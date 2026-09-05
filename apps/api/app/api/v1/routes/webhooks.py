"""Razorpay webhook receiver — HMAC-SHA256 verified on EVERY delivery before processing."""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.state_machine import capture_payment, open_case
from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.integrations import razorpay_client
from app.models.base import Customer, Invoice
from app.models.recovery import RecoveryCase, WebhookDelivery

log = get_logger("api.webhooks")
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/razorpay")
async def razorpay_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    raw = await request.body()
    signature = request.headers.get("x-razorpay-signature")
    try:
        body = json.loads(raw)
    except json.JSONDecodeError:
        body = {}
    event = body.get("event", "unknown")

    # Signature mandatory whenever any webhook secret exists (env or per-merchant); 401 otherwise.
    from app.models.settings import IntegrationSetting

    stored = (await db.execute(select(IntegrationSetting).where(IntegrationSetting.key == "rzp_webhook_secret"))).scalars().all()
    secrets_to_try = [get_settings().razorpay_webhook_secret] + [s.value for s in stored]
    live_keys = (await db.execute(select(IntegrationSetting).where(IntegrationSetting.key == "rzp_key_secret"))).scalars().all()
    any_secret = any(secrets_to_try)
    # Signature mandatory whenever a webhook secret OR live keys exist (env or per-merchant).
    sig_ok = (razorpay_client.verify_webhook_signature(raw, signature, secrets_to_try)
              if any_secret else not (razorpay_client.is_live() or live_keys))
    row = WebhookDelivery(event=event, signature_ok=sig_ok, payload=raw.decode(errors="replace")[:8000])
    db.add(row)
    await db.flush()
    if not sig_ok:
        row.error = "signature_verification_failed"
        await db.commit()
        raise HTTPException(401, "Invalid signature")

    try:
        await _handle(db, event, body)
        row.handled = event
    except Exception as e:
        row.error = str(e)[:280]
        log.error("webhook.handle_failed", webhook_event=event, error=str(e)[:200])
    await db.commit()
    return {"ok": True}


async def _handle(db: AsyncSession, event: str, body: dict[str, Any]) -> None:
    payment = (body.get("payload", {}).get("payment", {}) or {}).get("entity", {}) or {}
    subscription = (body.get("payload", {}).get("subscription", {}) or {}).get("entity", {}) or {}
    notes = payment.get("notes", {}) or {}

    if event == "payment.captured":
        invoice = (await db.execute(select(Invoice).where(Invoice.razorpay_order_id == payment.get("order_id"))
                                     .order_by(Invoice.created_at.desc()).limit(1))).scalars().first()
        if invoice:
            case = (await db.execute(select(RecoveryCase).where(RecoveryCase.invoice_id == invoice.id)
                                     .order_by(RecoveryCase.updated_at.desc()).limit(1))).scalar_one_or_none()
            if case:
                await capture_payment(db, case, payment["id"], payment.get("amount", invoice.amount_paise), source="webhook:payment.captured")
        return

    if event in ("payment.failed", "subscription.charged.failed"):
        email = notes.get("email") or (payment.get("email") or "")
        case_type = "subscription_failed" if event.startswith("subscription") else "payment_failed"
        code = payment.get("error_code") or payment.get("error_description") or ("subscription_charge_failed" if case_type == "subscription_failed" else "insufficient_funds")
        customer = (await db.execute(select(Customer).where(Customer.email == email.lower()))).scalars().first()
        if not customer:
            return  # unknown payer — nothing to recover against
        invoice = (await db.execute(select(Invoice).where(Invoice.customer_id == customer.id)
                                    .order_by(Invoice.due_date.desc()).limit(1))).scalars().first()
        if not invoice:
            invoice = Invoice(customer_id=customer.id, amount_paise=payment.get("amount", 0) or 100000,
                              due_date=__import__("datetime").datetime.now(__import__("datetime").timezone.utc))
            db.add(invoice)
            await db.flush()
        case = (await db.execute(select(RecoveryCase).where(RecoveryCase.invoice_id == invoice.id,
                                                           RecoveryCase.status.in_(("open", "escalated"))))).scalar_one_or_none()
        if not case:
            case = await open_case(db, customer, invoice, case_type, str(code)[:48], actor="razorpay")
        await db.commit()
        return

    if event in ("subscription.halted", "invoice.expired"):
        log.info("webhook.noted", event=event, sub=subscription.get("id"))
