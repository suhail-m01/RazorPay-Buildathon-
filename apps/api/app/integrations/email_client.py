"""Email delivery — Resend API or plain SMTP (e.g. Gmail app password), per-merchant creds.
No creds configured → queued (persisted honestly, never faked)."""
from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.settings import IntegrationCreds

log = get_logger("integ.email")


def _mask(email: str) -> str:
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}" if domain else email[:3] + "***"


def _smtp_send_sync(host: str, port: int, user: str, password: str, from_addr: str, to: str, subject: str, body: str) -> tuple[bool, str]:
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = from_addr, to, subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            smtp.starttls()
            smtp.login(user, password)
            smtp.send_message(msg)
        return True, "smtp"
    except smtplib.SMTPAuthenticationError:
        log.error("smtp.auth_failed", user=user[:3] + "***")
        return False, "smtp_auth_failed"
    except Exception as e:
        log.error("smtp.error", error=str(e)[:120])
        return False, "smtp_error"


async def send_email(to: str, subject: str, body: str, creds: IntegrationCreds | None = None) -> tuple[bool, str]:
    """Returns (delivered, provider). Raises never — the Act layer records the outcome."""
    c = creds
    if c is None:
        s = get_settings()
        c = IntegrationCreds(resend_api_key=s.resend_api_key, smtp_host=s.smtp_host if hasattr(s, "smtp_host") else "",
                             smtp_user="", smtp_pass="", email_from=s.email_from)
    from_addr = c.email_from or get_settings().email_from

    if c.resend_api_key:
        try:
            async with httpx.AsyncClient(timeout=15) as cl:
                r = await cl.post("https://api.resend.com/emails",
                                  headers={"Authorization": f"Bearer {c.resend_api_key}"},
                                  json={"from": from_addr, "to": [to], "subject": subject, "text": body})
                if r.status_code in (200, 201):
                    return True, "resend"
                log.error("email.resend_failed", status=r.status_code, body=r.text[:200])
                return False, "resend"
        except Exception as e:
            log.error("email.resend_error", error=str(e)[:120])
            return False, "resend"

    if c.smtp_host and c.smtp_user and c.smtp_pass:
        ok, provider = await asyncio.to_thread(
            _smtp_send_sync, c.smtp_host, c.smtp_port, c.smtp_user, c.smtp_pass, from_addr, to, subject, body)
        return ok, provider

    log.info("email.queued_no_provider", to=_mask(to), subject=subject[:60])
    return False, "queued"


async def send_test_email(creds: IntegrationCreds, to: str) -> tuple[bool, str]:
    ok, provider = await send_email(
        to, "RecoverPay AI — email channel connected",
        "Your email channel is live. Recovery messages and receipts will arrive from this pipeline.\n\n— RecoverPay AI",
        creds,
    )
    if provider == "smtp_auth_failed":
        return False, "SMTP rejected the login — check the app password"
    if provider == "queued":
        return False, "No email provider configured yet"
    return ok, f"Test email sent to {to} via {provider}" if ok else f"Send failed ({provider})"
