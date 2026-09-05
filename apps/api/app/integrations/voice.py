"""Outbound recovery voice: Vonage Voice API first, Twilio fallback."""
from __future__ import annotations

from html import escape
from pathlib import Path
import time

import httpx
import jwt

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger("integ.voice")


def _normalize_phone(value: str) -> str:
    v = (value or "").strip().replace(" ", "")
    if v.startswith("tel:"):
        v = v[4:]
    if not v.startswith("+"):
        if v.startswith("91") and len(v) == 12:
            v = "+" + v
        elif len(v) == 10:
            v = "+91" + v
    return v


def _digits(value: str) -> str:
    return _normalize_phone(value).lstrip("+")


def _load_private_key(path_value: str) -> str | None:
    path = Path(path_value)
    if not path.is_absolute():
        path = Path.cwd() / path
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _vonage_jwt(application_id: str, private_key: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {"application_id": application_id, "iat": now, "exp": now + 300, "jti": f"recoverpay-voice-{now}"},
        private_key, algorithm="RS256", headers={"typ": "JWT"},
    )


def _vonage_creds(creds=None):
    if creds is not None and getattr(creds, "vonage_voice_ready", False):
        return creds.vonage_application_id, creds.vonage_private_key_path, creds.vonage_voice_from
    s = get_settings()
    if s.vonage_application_id and s.vonage_private_key_path and s.vonage_voice_from:
        return s.vonage_application_id, s.vonage_private_key_path, s.vonage_voice_from
    return None


def _twilio_creds(creds=None):
    if creds is not None and getattr(creds, "twilio_voice_ready", False):
        return creds.twilio_sid, creds.twilio_token, creds.twilio_voice_from
    s = get_settings()
    if s.twilio_account_sid and s.twilio_auth_token and s.twilio_voice_from:
        return s.twilio_account_sid, s.twilio_auth_token, s.twilio_voice_from
    return None


def _vonage_error(r: httpx.Response) -> str:
    try:
        j = r.json()
        detail = j.get("detail") or j.get("title") or str(j)
        return f"vonage:{r.status_code}:{str(detail)[:180]}"
    except Exception:
        return f"vonage:{r.status_code}:{r.text[:180]}"


def _twilio_error(r: httpx.Response) -> str:
    try:
        j = r.json()
        return f"twilio:{j.get('code', r.status_code)}:{str(j.get('message', ''))[:180]}"
    except Exception:
        return f"twilio:{r.status_code}:{r.text[:180]}"


def _twiml(script: str, language: str = "en-IN") -> str:
    text = escape((script or "")[:1800])
    lang = language if language in {"en-IN", "hi-IN", "ta-IN", "te-IN", "mr-IN"} else "en-IN"
    return f'<Response><Say language="{lang}">{text}</Say><Pause length="1"/><Say language="{lang}">Thank you. Please use the secure payment link already shared with you. Goodbye.</Say></Response>'


async def _place_vonage(to: str, script: str, creds=None) -> tuple[bool, str, str | None]:
    cfg = _vonage_creds(creds)
    if not cfg:
        return False, "vonage:config:not configured", None
    application_id, key_path, from_number = cfg
    private_key = _load_private_key(key_path)
    if not private_key:
        return False, f"vonage:config:private key not found at {key_path}", None

    to_number, from_number = _digits(to), _digits(from_number)
    if not to_number or not from_number:
        return False, "vonage:config:voice numbers must be E.164", None

    payload: dict = {
        "to": [{"type": "phone", "number": to_number}],
        "from": {"type": "phone", "number": from_number},
        "ncco": [
            {"action": "talk", "text": (script or "")[:1800]},
            {"action": "talk", "text": "Thank you. Please use the secure payment link already shared with you. Goodbye."},
        ],
    }
    s = get_settings()
    if s.public_base_url:
        payload["event_url"] = [s.public_base_url.rstrip("/") + "/api/v1/webhooks/vonage/voice/event"]
        payload["event_method"] = "POST"

    token = _vonage_jwt(application_id, private_key)
    async with httpx.AsyncClient(timeout=25) as client:
        r = await client.post(
            "https://api.nexmo.com/v1/calls",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
        )
    if r.status_code in (200, 201, 202):
        try:
            call_id = r.json().get("uuid")
        except Exception:
            call_id = None
        return True, "vonage", call_id
    log.error("vonage.voice_failed", status=r.status_code, body=r.text[:200])
    return False, _vonage_error(r), None


async def _place_twilio(to: str, script: str, language: str, creds=None) -> tuple[bool, str, str | None]:
    cfg = _twilio_creds(creds)
    if not cfg:
        return False, "twilio:config:not configured", None
    sid, token, from_number = cfg
    to_number, from_number = _normalize_phone(to), _normalize_phone(from_number)
    if not to_number.startswith("+") or not from_number.startswith("+"):
        return False, "twilio:config:voice numbers must be E.164", None
    data = {"To": to_number, "From": from_number, "Twiml": _twiml(script, language)}
    s = get_settings()
    if s.public_base_url:
        data.update({
            "StatusCallback": s.public_base_url.rstrip("/") + "/api/v1/webhooks/twilio/voice/status",
            "StatusCallbackMethod": "POST",
            "StatusCallbackEvent": ["initiated", "ringing", "answered", "completed"],
        })
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Calls.json", auth=(sid, token), data=data
        )
    if r.status_code in (200, 201):
        try:
            call_id = r.json().get("sid")
        except Exception:
            call_id = None
        return True, "twilio", call_id
    log.error("twilio.voice_failed", status=r.status_code, body=r.text[:200])
    return False, _twilio_error(r), None


async def place_call(to: str, script: str, language: str = "en-IN", creds=None) -> tuple[bool, str, str | None]:
    """Place one policy-approved recovery call. Vonage is primary; Twilio remains fallback."""
    if _vonage_creds(creds):
        ok, provider, call_id = await _place_vonage(to, script, creds=creds)
        if ok:
            return ok, provider, call_id
        if not provider.startswith("vonage:config:"):
            return False, provider, call_id
    return await _place_twilio(to, script, language, creds=creds)
