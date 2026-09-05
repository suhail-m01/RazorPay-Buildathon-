"""Settings endpoints: masked status, save credentials, real connection tests."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.config import get_settings
from app.integrations import email_client, razorpay_client
from app.models.base import MerchantUser
from app.models.settings import IntegrationCreds, load_creds, save_creds

router = APIRouter(prefix="/setup", tags=["setup"])


def _mask(value: str, visible: int = 6) -> str:
    if not value:
        return ""
    return value[:visible] + "…" + value[-2:] if len(value) > visible + 4 else "set"


class CredsIn(BaseModel):
    rzp_key_id: str | None = None
    rzp_key_secret: str | None = None
    rzp_webhook_secret: str | None = None
    resend_api_key: str | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_user: str | None = None
    smtp_pass: str | None = None
    email_from: str | None = None
    gemini_api_key: str | None = None
    twilio_sid: str | None = None
    twilio_token: str | None = None
    twilio_whatsapp_from: str | None = None
    twilio_whatsapp_content_sid: str | None = None
    twilio_whatsapp_content_variables_json: str | None = None
    twilio_voice_from: str | None = None
    twilio_voice_to: str | None = None
    vonage_application_id: str | None = None
    vonage_private_key_path: str | None = None
    vonage_whatsapp_from: str | None = None
    vonage_whatsapp_to: str | None = None
    vonage_voice_from: str | None = None
    vonage_voice_to: str | None = None


@router.get("")
async def setup_status(db: AsyncSession = Depends(get_db), user: MerchantUser = Depends(get_current_user)):
    c = await load_creds(db, user.merchant_id)
    return {
        "ok": True,
        "razorpay": {"ready": c.razorpay_ready, "key_id": _mask(c.rzp_key_id), "webhook_secret_set": bool(c.rzp_webhook_secret)},
        "email": {"ready": c.email_ready, "mode": "resend" if c.resend_api_key else ("smtp" if c.smtp_host else "none"),
                  "from": c.email_from, "smtp_host": c.smtp_host, "smtp_user": _mask(c.smtp_user)},
        "ai": {"ready": c.llm_ready, "provider": "gemini" if c.gemini_api_key else "rules-only"},
        "whatsapp": {"ready": c.whatsapp_ready, "provider": c.whatsapp_provider, "sid": _mask(c.twilio_sid), "from": c.twilio_whatsapp_from, "content_sid": _mask(c.twilio_whatsapp_content_sid)},
        "vonage": {"ready": c.vonage_ready, "application_id": _mask(c.vonage_application_id), "from": c.vonage_whatsapp_from},
        "voice": {"ready": c.voice_ready, "provider": c.voice_provider,
                  "from": _mask(c.vonage_voice_from or c.twilio_voice_from),
                  "to": _mask(c.vonage_voice_to or c.twilio_voice_to)},
    }


@router.put("")
async def save_setup(body: CredsIn, db: AsyncSession = Depends(get_db), user: MerchantUser = Depends(get_current_user)):
    patch = body.model_dump(exclude_none=True)
    sid = (patch.get("twilio_sid") or "").strip()
    if sid and not (sid.startswith("AC") and len(sid) == 34):
        return {"ok": False, "message": "Twilio Account SID must start with AC and be 34 characters."}
    c = await save_creds(db, user.merchant_id, patch)
    return {"ok": True, "razorpay_ready": c.razorpay_ready, "email_ready": c.email_ready,
            "whatsapp_ready": c.whatsapp_ready, "voice_ready": c.voice_ready}


@router.post("/test-razorpay")
async def test_razorpay(db: AsyncSession = Depends(get_db), user: MerchantUser = Depends(get_current_user)):
    c = await load_creds(db, user.merchant_id)
    ok, message = await razorpay_client.fetch_key_validity(c)
    return {"ok": ok, "message": message}


@router.post("/test-email")
async def test_email(body: dict, db: AsyncSession = Depends(get_db), user: MerchantUser = Depends(get_current_user)):
    to = (body or {}).get("to", "")
    if "@" not in to:
        return {"ok": False, "message": "Enter a valid email address"}
    c: IntegrationCreds = await load_creds(db, user.merchant_id)
    ok, message = await email_client.send_test_email(c, to)
    return {"ok": ok, "message": message}


@router.post("/test-llm")
async def test_llm(db: AsyncSession = Depends(get_db), user: MerchantUser = Depends(get_current_user)):
    """Real Gemini round-trip: classify a sample failure through the actual diagnosis prompt."""
    c = await load_creds(db, user.merchant_id)
    if not c.gemini_api_key:
        env = get_settings().gemini_api_key
        if not env:
            return {"ok": False, "message": "No Gemini key set — add one (free at aistudio.google.com/apikey)"}
        c.gemini_api_key = env
    from app.agent.diagnose import diagnose

    d = await diagnose("payment_failed", "insufficient_funds", 249900, gemini_key=c.gemini_api_key)
    return {"ok": d.get("engine") == "llm", "engine": d.get("engine"),
            "message": f"LLM active — root cause '{d['root_cause']}' at {d['confidence']:.0%} confidence" if d.get("engine") == "llm"
            else f"Key set but LLM call failed — falling back to rules ({d.get('engine')})"}


@router.post("/test-whatsapp")
async def test_whatsapp(body: dict, db: AsyncSession = Depends(get_db), user: MerchantUser = Depends(get_current_user)):
    """Send a real WhatsApp via Twilio. Trial accounts require a Twilio template."""
    to = (body or {}).get("to", "")
    if "+" not in to:
        return {"ok": False, "message": "Enter the recipient's WhatsApp number (+91…)"}
    c = await load_creds(db, user.merchant_id)
    if not c.whatsapp_ready:
        return {"ok": False, "message": "Twilio WhatsApp not configured — add SID, auth token and WhatsApp sender"}
    from app.integrations.messaging import send_whatsapp
    ok, provider = await send_whatsapp(to, "RecoverPay AI — WhatsApp channel connected.", creds=c)
    if ok:
        return {"ok": True, "message": f"WhatsApp request accepted by Twilio for {to} ✓"}
    if provider == "queued":
        return {"ok": False, "message": "Twilio not configured"}
    detail = provider.split(":", 2)[-1] if ":" in provider else provider
    if "63015" in provider or "sandbox" in detail.lower():
        return {"ok": False, "message": "Recipient must join your Twilio WhatsApp trial/sandbox first (use the join code shown in Twilio)."}
    return {"ok": False, "message": f"Twilio rejected WhatsApp: {detail}"}


@router.post("/test-vonage-whatsapp")
async def test_vonage_whatsapp(body: dict, db: AsyncSession = Depends(get_db), user: MerchantUser = Depends(get_current_user)):
    c = await load_creds(db, user.merchant_id)
    if not c.vonage_ready:
        return {"ok": False, "message": "Vonage is not configured: set Application ID, private key path and WhatsApp sandbox sender."}
    from app.integrations.messaging import send_vonage_whatsapp
    to = str(body.get("to") or c.vonage_whatsapp_to or "").strip()
    if not to:
        return {"ok": False, "message": "Enter a WhatsApp destination number."}
    ok, provider = await send_vonage_whatsapp(to, "RecoverPay AI — Vonage WhatsApp channel connected.", creds=c)
    return {"ok": ok, "message": "Vonage WhatsApp message accepted." if ok else f"Vonage WhatsApp failed: {provider}"}


@router.post("/test-voice")
async def test_voice(body: dict, db: AsyncSession = Depends(get_db), user: MerchantUser = Depends(get_current_user)):
    """Place a real test call through the same provider used by the agent (Vonage first)."""
    c = await load_creds(db, user.merchant_id)
    if not c.voice_ready:
        return {"ok": False, "message": "Voice is not configured — add a Vonage Voice From number (or keep Twilio Voice as fallback)."}
    to = str((body or {}).get("to") or c.vonage_voice_to or c.twilio_voice_to or "").strip()
    if not to:
        return {"ok": False, "message": "Enter a destination number in E.164 format (+91…)."}
    from app.integrations.voice import place_call
    script = "Hello. This is a RecoverPay AI test call. Your autonomous recovery voice channel is connected successfully."
    ok, provider, call_sid = await place_call(to, script, "en-IN", creds=c)
    if ok:
        return {"ok": True, "message": f"{provider.title()} accepted the call request ✓", "call_sid": call_sid}
    detail = provider.split(":", 2)[-1] if ":" in provider else provider
    return {"ok": False, "message": f"Voice call failed: {detail}"}
