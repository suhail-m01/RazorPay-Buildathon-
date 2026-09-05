"""Per-merchant integration settings, DB-backed with env fallback.

Real-product behaviour: the merchant pastes THEIR Razorpay test keys and email SMTP
credentials in Settings; every send/order uses those. Env vars act only as fallback."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.base import Base, Merchant

log = get_logger("core.integrations")


@dataclass
class IntegrationCreds:
    rzp_key_id: str = ""
    rzp_key_secret: str = ""
    rzp_webhook_secret: str = ""
    resend_api_key: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    email_from: str = ""
    gemini_api_key: str = ""
    twilio_sid: str = ""
    twilio_token: str = ""
    twilio_whatsapp_from: str = ""
    twilio_whatsapp_content_sid: str = ""
    twilio_whatsapp_content_variables_json: str = ""
    twilio_voice_from: str = ""
    twilio_voice_to: str = ""
    vonage_application_id: str = ""
    vonage_private_key_path: str = "./private.key"
    vonage_whatsapp_from: str = ""
    vonage_whatsapp_to: str = ""
    vonage_voice_from: str = ""
    vonage_voice_to: str = ""

    @property
    def razorpay_ready(self) -> bool:
        return bool(self.rzp_key_id and self.rzp_key_secret)

    @property
    def email_ready(self) -> bool:
        return bool(self.resend_api_key or (self.smtp_host and self.smtp_user and self.smtp_pass))

    @property
    def llm_ready(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def whatsapp_ready(self) -> bool:
        return self.twilio_ready or self.vonage_ready

    @property
    def twilio_ready(self) -> bool:
        return bool(self.twilio_sid and self.twilio_token and self.twilio_whatsapp_from)

    @property
    def vonage_ready(self) -> bool:
        return bool(self.vonage_application_id and self.vonage_private_key_path and self.vonage_whatsapp_from)

    @property
    def whatsapp_provider(self) -> str:
        if self.vonage_ready:
            return "vonage"
        if self.twilio_ready:
            return "twilio"
        return "none"

    @property
    def vonage_voice_ready(self) -> bool:
        return bool(self.vonage_application_id and self.vonage_private_key_path and self.vonage_voice_from)

    @property
    def twilio_voice_ready(self) -> bool:
        return bool(self.twilio_sid and self.twilio_token and self.twilio_voice_from)

    @property
    def voice_ready(self) -> bool:
        return self.vonage_voice_ready or self.twilio_voice_ready

    @property
    def voice_provider(self) -> str:
        if self.vonage_voice_ready:
            return "vonage"
        if self.twilio_voice_ready:
            return "twilio"
        return "none"


async def load_creds(db: AsyncSession, merchant_id: str | None) -> IntegrationCreds:
    """DB values override env; env is the fallback so the app also runs from .env."""
    env = get_settings()
    c = IntegrationCreds(
        rzp_key_id=env.razorpay_key_id, rzp_key_secret=env.razorpay_key_secret,
        rzp_webhook_secret=env.razorpay_webhook_secret, resend_api_key=env.resend_api_key,
        email_from=env.email_from,
        twilio_sid=env.twilio_account_sid, twilio_token=env.twilio_auth_token,
        twilio_whatsapp_from=env.twilio_from_whatsapp,
        twilio_whatsapp_content_sid=env.twilio_whatsapp_content_sid,
        twilio_whatsapp_content_variables_json=env.twilio_whatsapp_content_variables_json,
        twilio_voice_from=env.twilio_voice_from, twilio_voice_to=env.twilio_voice_to,
        vonage_application_id=env.vonage_application_id, vonage_private_key_path=env.vonage_private_key_path,
        vonage_whatsapp_from=env.vonage_whatsapp_from, vonage_whatsapp_to=env.vonage_whatsapp_to,
        vonage_voice_from=env.vonage_voice_from, vonage_voice_to=env.vonage_voice_to,
    )
    if merchant_id:
        from app.models.settings import IntegrationSetting

        rows = (await db.execute(select(IntegrationSetting).where(IntegrationSetting.merchant_id == merchant_id))).scalars().all()
        kv = {r.key: r.value for r in rows}
        if kv.get("rzp_key_id"):
            c.rzp_key_id, c.rzp_key_secret = kv["rzp_key_id"], kv.get("rzp_key_secret", "")
        if kv.get("rzp_webhook_secret"):
            c.rzp_webhook_secret = kv["rzp_webhook_secret"]
        if kv.get("resend_api_key"):
            c.resend_api_key = kv["resend_api_key"]
        if kv.get("smtp_host"):
            c.smtp_host, c.smtp_user, c.smtp_pass = kv["smtp_host"], kv.get("smtp_user", ""), kv.get("smtp_pass", "")
            try:
                c.smtp_port = int(kv.get("smtp_port", "587"))
            except ValueError:
                c.smtp_port = 587
        if kv.get("email_from"):
            c.email_from = kv["email_from"]
        if kv.get("gemini_api_key"):
            c.gemini_api_key = kv["gemini_api_key"]
        if kv.get("twilio_sid"):
            c.twilio_sid, c.twilio_token = kv["twilio_sid"], kv.get("twilio_token", "")
        if kv.get("twilio_token") and not c.twilio_token:
            c.twilio_token = kv["twilio_token"]
        if kv.get("twilio_whatsapp_from"):
            c.twilio_whatsapp_from = kv["twilio_whatsapp_from"]
        if kv.get("twilio_whatsapp_content_sid"):
            c.twilio_whatsapp_content_sid = kv["twilio_whatsapp_content_sid"]
        if kv.get("twilio_whatsapp_content_variables_json"):
            c.twilio_whatsapp_content_variables_json = kv["twilio_whatsapp_content_variables_json"]
        if kv.get("twilio_voice_from"):
            c.twilio_voice_from = kv["twilio_voice_from"]
        if kv.get("twilio_voice_to"):
            c.twilio_voice_to = kv["twilio_voice_to"]
        if kv.get("vonage_application_id"):
            c.vonage_application_id = kv["vonage_application_id"]
        if kv.get("vonage_private_key_path"):
            c.vonage_private_key_path = kv["vonage_private_key_path"]
        if kv.get("vonage_whatsapp_from"):
            c.vonage_whatsapp_from = kv["vonage_whatsapp_from"]
        if kv.get("vonage_whatsapp_to"):
            c.vonage_whatsapp_to = kv["vonage_whatsapp_to"]
        if kv.get("vonage_voice_from"):
            c.vonage_voice_from = kv["vonage_voice_from"]
        if kv.get("vonage_voice_to"):
            c.vonage_voice_to = kv["vonage_voice_to"]
    return c


async def save_creds(db: AsyncSession, merchant_id: str, patch: dict[str, Any]) -> IntegrationCreds:
    from app.models.settings import IntegrationSetting

    allowed = {"rzp_key_id", "rzp_key_secret", "rzp_webhook_secret", "resend_api_key",
               "smtp_host", "smtp_port", "smtp_user", "smtp_pass", "email_from",
               "gemini_api_key", "twilio_sid", "twilio_token", "twilio_whatsapp_from",
               "twilio_whatsapp_content_sid", "twilio_whatsapp_content_variables_json", "twilio_voice_from", "twilio_voice_to",
               "vonage_application_id", "vonage_private_key_path", "vonage_whatsapp_from", "vonage_whatsapp_to",
               "vonage_voice_from", "vonage_voice_to"}
    existing = (await db.execute(select(IntegrationSetting).where(IntegrationSetting.merchant_id == merchant_id))).scalars().all()
    by_key = {r.key: r for r in existing}
    for k, v in patch.items():
        if k not in allowed or v is None:
            continue
        value = str(v).strip()
        if not value:
            continue
        if k in by_key:
            by_key[k].value = value
        else:
            db.add(IntegrationSetting(merchant_id=merchant_id, key=k, value=value))
    await db.commit()
    log.info("creds.updated", merchant=merchant_id, fields=[k for k in patch if k in allowed])
    return await load_creds(db, merchant_id)


async def merchant_name(db: AsyncSession, merchant_id: str) -> str:
    m = await db.get(Merchant, merchant_id)
    return m.name if m else "the merchant"


class IntegrationSetting(Base):
    """key/value credential store per merchant (values are secrets — never returned unmasked)."""

    __tablename__ = "integration_settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    key: Mapped[str] = mapped_column(String(48))
    value: Mapped[str] = mapped_column(String(400))
