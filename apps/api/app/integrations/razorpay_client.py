"""Razorpay client — per-merchant creds (DB) with env fallback. Real Orders/Payment Links
via httpx, HMAC webhook verify, order-payment status sync (real failure detection), and a
local order fallback that flows through the SAME capture path when keys are absent."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.settings import IntegrationCreds

log = get_logger("integ.razorpay")
BASE = "https://api.razorpay.com/v1"


def is_live(creds: IntegrationCreds | None = None) -> bool:
    if creds is not None:
        return creds.razorpay_ready
    s = get_settings()
    return bool(s.razorpay_key_id and s.razorpay_key_secret)


def _env_creds() -> IntegrationCreds:
    s = get_settings()
    return IntegrationCreds(rzp_key_id=s.razorpay_key_id, rzp_key_secret=s.razorpay_key_secret,
                            rzp_webhook_secret=s.razorpay_webhook_secret)


async def create_order(amount_paise: int, receipt: str, notes: dict[str, str] | None = None,
                       creds: IntegrationCreds | None = None) -> dict[str, Any]:
    c = creds or _env_creds()
    if c.razorpay_ready:
        async with httpx.AsyncClient(timeout=15) as cl:
            r = await cl.post(f"{BASE}/orders", auth=(c.rzp_key_id, c.rzp_key_secret),
                              json={"amount": amount_paise, "currency": "INR", "receipt": receipt, "notes": notes or {}})
            if r.status_code == 200:
                j = r.json()
                return {"order_id": j["id"], "amount_paise": j["amount"], "provider": "razorpay", "key_id": c.rzp_key_id, "error": None}
            reason = str(r.json().get("error", {}).get("description", r.text[:120]))
            log.error("razorpay.order_failed", status=r.status_code, body=r.text[:200])
            return {"order_id": f"order_local_{secrets.token_hex(8)}", "amount_paise": amount_paise,
                    "provider": "local", "key_id": c.rzp_key_id, "error": reason}
    return {"order_id": f"order_local_{secrets.token_hex(8)}", "amount_paise": amount_paise,
            "provider": "local", "key_id": c.rzp_key_id, "error": None}


async def create_payment_link(amount_paise: int, receipt: str, base_url: str,
                              customer: dict[str, str] | None = None,
                              creds: IntegrationCreds | None = None) -> dict[str, Any]:
    c = creds or _env_creds()
    order = await create_order(amount_paise, receipt, notes={"receipt": receipt}, creds=c)
    if c.razorpay_ready:
        # Hosted rzp.io link bound to OUR order (options.order_id) — payments land on the
        # order, so /orders/{id}/payments sync and webhooks both track them. We send the
        # emails ourselves, so Razorpay's own notifications stay off.
        payload = {
            "amount": amount_paise, "currency": "INR", "reference_id": receipt,
            "description": "RecoverPay payment",
            "options": {"order_id": order["order_id"]},
            "notify": {"sms": False, "email": False},
        }
        async with httpx.AsyncClient(timeout=15) as cl:
            r = await cl.post(f"{BASE}/payment_links", auth=(c.rzp_key_id, c.rzp_key_secret), json=payload)
            if r.status_code in (200, 201):
                j = r.json()
                if j.get("short_url"):
                    return {"url": j["short_url"], "order_id": order["order_id"],
                            "provider": "razorpay", "link_id": j.get("id")}
            log.warning("razorpay.link_unavailable_using_app_pay_page", status=r.status_code, body=r.text[:150])
            # Fallback: our own pay page opens Checkout.js on THIS order — fully trackable.
            return {"url": f"{base_url.rstrip('/')}/pay/{order['order_id']}", "order_id": order["order_id"],
                    "provider": "razorpay-app-checkout", "link_id": None, "error": order.get("error")}
    return {"url": f"{base_url.rstrip('/')}/pay/{order['order_id']}", "order_id": order["order_id"],
            "provider": order["provider"], "link_id": None}


async def fetch_order_payments(order_id: str, creds: IntegrationCreds | None = None) -> list[dict[str, Any]] | None:
    """REAL payment attempts for an order (Razorpay API). None when not live/unreachable —
    the caller then keeps local state unchanged rather than guessing."""
    c = creds or _env_creds()
    if not c.razorpay_ready or order_id.startswith("order_local"):
        return None
    try:
        async with httpx.AsyncClient(timeout=15) as cl:
            r = await cl.get(f"{BASE}/orders/{order_id}/payments", auth=(c.rzp_key_id, c.rzp_key_secret))
            if r.status_code == 200:
                items = r.json().get("items", [])
                return [{"id": p.get("id"), "status": p.get("status"), "amount": p.get("amount"),
                         "error_code": p.get("error_code"), "error_description": p.get("error_description"),
                         "method": p.get("method")} for p in items]
            log.warning("razorpay.fetch_payments_failed", status=r.status_code)
    except Exception as e:
        log.warning("razorpay.fetch_payments_error", error=str(e)[:120])
    return None


async def fetch_key_validity(creds: IntegrationCreds) -> tuple[bool, str]:
    """Settings 'Test connection' — hits a real authenticated endpoint."""
    if not creds.razorpay_ready:
        return False, "Keys not set"
    try:
        async with httpx.AsyncClient(timeout=12) as cl:
            r = await cl.get(f"{BASE}/payments?count=1", auth=(creds.rzp_key_id, creds.rzp_key_secret))
            if r.status_code == 200:
                return True, "Razorpay keys valid (test mode)" if creds.rzp_key_id.startswith("rzp_test") else "Razorpay keys valid"
            if r.status_code == 401:
                return False, "Invalid key id / secret"
            return False, f"Razorpay responded {r.status_code}"
    except Exception as e:
        return False, f"Could not reach Razorpay: {str(e)[:80]}"


def verify_webhook_signature(raw_body: bytes, signature: str | None, secrets_to_try: list[str]) -> bool:
    for secret in [s for s in secrets_to_try if s]:
        expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
        if signature and hmac.compare_digest(expected, signature):
            return True
    return False


def verify_checkout_signature(order_id: str, payment_id: str, signature: str, creds: IntegrationCreds | None = None) -> bool:
    c = creds or _env_creds()
    if not c.rzp_key_secret:
        return False
    expected = hmac.new(c.rzp_key_secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def local_payment_id() -> str:
    return f"pay_test_{secrets.token_hex(8)}"
