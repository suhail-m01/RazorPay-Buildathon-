"""Outbound messaging integrations: Vonage WhatsApp first, Twilio fallback."""
from __future__ import annotations

import json
from pathlib import Path
import time

import httpx
import jwt

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger("integ.messaging")


def _whatsapp_creds(creds):
    if creds is not None and creds.whatsapp_ready:
        return (
            creds.twilio_sid,
            creds.twilio_token,
            creds.twilio_whatsapp_from,
            creds.twilio_whatsapp_content_sid,
            creds.twilio_whatsapp_content_variables_json,
        )

    s = get_settings()

    if s.twilio_account_sid and s.twilio_auth_token and s.twilio_from_whatsapp:
        return (
            s.twilio_account_sid,
            s.twilio_auth_token,
            s.twilio_from_whatsapp,
            s.twilio_whatsapp_content_sid,
            s.twilio_whatsapp_content_variables_json,
        )

    return None


def _vonage_creds(creds):
    if creds is not None and creds.vonage_ready:
        return (
            creds.vonage_application_id,
            creds.vonage_private_key_path,
            creds.vonage_whatsapp_from,
        )

    s = get_settings()

    if (
        s.vonage_application_id
        and s.vonage_private_key_path
        and s.vonage_whatsapp_from
    ):
        return (
            s.vonage_application_id,
            s.vonage_private_key_path,
            s.vonage_whatsapp_from,
        )

    return None


def _normalize_wa(to: str) -> str:
    v = (to or "").strip().replace(" ", "")

    if v.startswith("whatsapp:"):
        v = v[9:]

    if v.startswith("+"):
        v = v[1:]

    return v


def _normalize_phone(to: str) -> str:
    v = (to or "").strip().replace(" ", "")

    if v.startswith("whatsapp:"):
        v = v[9:]

    if not v.startswith("+"):
        if len(v) == 10:
            v = "+91" + v
        elif v.startswith("91"):
            v = "+" + v

    return v


def _twilio_error(r: httpx.Response) -> str:
    try:
        err = r.json()
        return f"twilio:{err.get('code', '?')}:{str(err.get('message', ''))[:180]}"
    except Exception:
        return f"twilio:{r.status_code}:{r.text[:180]}"


def _vonage_error(r: httpx.Response) -> str:
    try:
        err = r.json()
        detail = (
            err.get("detail")
            or err.get("title")
            or err.get("type")
            or str(err)
        )
        return f"vonage:{r.status_code}:{str(detail)[:180]}"
    except Exception:
        return f"vonage:{r.status_code}:{r.text[:180]}"


def _load_private_key(path_value: str) -> str | None:
    p = Path(path_value)

    if not p.is_absolute():
        p = Path.cwd() / p

    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return None


def _vonage_jwt(application_id: str, private_key: str) -> str:
    now = int(time.time())

    payload = {
        "application_id": application_id,
        "iat": now,
        "exp": now + 300,
        "jti": f"recoverpay-{now}",
    }

    return jwt.encode(
        payload,
        private_key,
        algorithm="RS256",
        headers={"typ": "JWT"},
    )


async def send_vonage_whatsapp(
    to: str,
    body: str,
    creds=None,
) -> tuple[bool, str]:

    cfg = _vonage_creds(creds)

    if not cfg:
        return False, "vonage:config:not configured"

    application_id, key_path, from_addr = cfg

    private_key = _load_private_key(key_path)

    if not private_key:
        return False, f"vonage:config:private key not found at {key_path}"

    token = _vonage_jwt(application_id, private_key)

    payload = {
    "from": _normalize_wa(from_addr),
    "to": _normalize_wa(to),
    "channel": "whatsapp",
    "message_type": "text",
    "text": (body or "")[:1000],
    }   

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(
            "https://messages-sandbox.nexmo.com/v1/messages",
            headers=headers,
            json=payload,
        )

    if r.status_code in (200, 201, 202):
        return True, "vonage"

    log.error(
        "vonage.whatsapp_failed",
        status=r.status_code,
        body=r.text[:200],
    )

    return False, _vonage_error(r)


async def send_sms(
    to: str,
    body: str,
    creds=None,
) -> tuple[bool, str]:

    cfg = _whatsapp_creds(creds)
    s = get_settings()

    if cfg is None or not s.twilio_from_sms:
        log.info(
            "sms.queued_no_provider",
            to=to[:6] + "***",
        )
        return False, "queued"

    sid, token = cfg[0], cfg[1]

    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            auth=(sid, token),
            data={
                "To": to,
                "From": s.twilio_from_sms,
                "Body": body,
            },
        )

    if r.status_code in (200, 201):
        return True, "twilio"

    log.error(
        "twilio.sms_failed",
        status=r.status_code,
        body=r.text[:150],
    )

    return False, _twilio_error(r)


async def send_whatsapp(
    to: str,
    body: str,
    creds=None,
) -> tuple[bool, str]:

    vcfg = _vonage_creds(creds)

    if vcfg:
        ok, provider = await send_vonage_whatsapp(
            to,
            body,
            creds=creds,
        )

        if ok:
            return True, provider

        if not provider.startswith("vonage:config:"):
            return False, provider

    cfg = _whatsapp_creds(creds)

    if cfg is None:
        log.info(
            "whatsapp.queued_no_provider",
            to=to[:6] + "***",
        )
        return False, "queued"

    sid, token, from_addr, content_sid, content_vars = cfg

    data = {
        "To": _normalize_wa(to),
        "From": from_addr,
    }

    if content_sid:
        if content_vars:
            try:
                data["ContentVariables"] = json.dumps(
                    json.loads(content_vars)
                )
            except Exception:
                return (
                    False,
                    "twilio:config:TWILIO_WHATSAPP_CONTENT_VARIABLES_JSON is invalid JSON",
                )

        data["ContentSid"] = content_sid
    else:
        data["Body"] = body

    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            auth=(sid, token),
            data=data,
        )

    if r.status_code in (200, 201):
        return True, "twilio"

    log.error(
        "twilio.whatsapp_failed",
        status=r.status_code,
        body=r.text[:180],
    )

    return False, _twilio_error(r)