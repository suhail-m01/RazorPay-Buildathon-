"""Public pay page backend: order info + signature-verified checkout completion.
The HMAC signature IS the authentication — emailed links work without a login."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.state_machine import capture_payment
from app.core.db import get_db
from app.core.deps import client_ip
from app.core.ratelimit import rate_limit
from app.integrations import razorpay_client
from app.models.base import Customer, Invoice
from app.models.recovery import Receipt
from app.models.settings import load_creds

router = APIRouter(prefix="/pay", tags=["pay"])


async def _invoice_by_order(db: AsyncSession, order_id: str) -> Invoice:
    inv = (await db.execute(select(Invoice).where(Invoice.razorpay_order_id == order_id).order_by(Invoice.created_at.desc()).limit(1))).scalars().first()
    if not inv:
        raise HTTPException(404, "Unknown order")
    return inv


@router.get("/{order_id}/info")
async def order_info(order_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    if not await rate_limit(f"payinfo:{await client_ip(request)}", 30, 60):
        raise HTTPException(429, "Too many requests")
    inv = await _invoice_by_order(db, order_id)
    cust = await db.get(Customer, inv.customer_id)
    creds = await load_creds(db, cust.merchant_id)
    return {"ok": True, "amount_paise": inv.amount_paise, "key_id": creds.rzp_key_id or "",
            "checkout_live": creds.razorpay_ready, "customer_name": cust.name}


class CompleteIn(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str = Field(min_length=6)
    razorpay_signature: str


@router.post("/complete")
async def complete(body: CompleteIn, request: Request, db: AsyncSession = Depends(get_db)):
    if not await rate_limit(f"paydone:{await client_ip(request)}", 20, 60):
        raise HTTPException(429, "Too many requests")
    inv = await _invoice_by_order(db, body.razorpay_order_id)
    cust = await db.get(Customer, inv.customer_id)
    creds = await load_creds(db, cust.merchant_id)
    if not creds.razorpay_ready:
        raise HTTPException(400, "Razorpay not configured for this merchant")
    if not razorpay_client.verify_checkout_signature(body.razorpay_order_id, body.razorpay_payment_id,
                                                     body.razorpay_signature, creds):
        raise HTTPException(400, "Signature verification failed")

    case = (await db.execute(select(__import__("app.models.recovery", fromlist=["RecoveryCase"]).RecoveryCase)
                             .where(__import__("app.models.recovery", fromlist=["RecoveryCase"]).RecoveryCase.invoice_id == inv.id)
                             .order_by(__import__("app.models.recovery", fromlist=["RecoveryCase"]).RecoveryCase.updated_at.desc())
                             .limit(1))).scalar_one_or_none()
    if case:
        res = await capture_payment(db, case, body.razorpay_payment_id, inv.amount_paise, source="checkout:emailed-link")
        return {"ok": True, **res}

    existing = (await db.execute(select(Receipt).where(Receipt.payment_id == body.razorpay_payment_id))).scalar_one_or_none()
    if existing:
        return {"ok": True, "receipt_id": existing.id, "already": True}
    inv.status, inv.razorpay_payment_id = "paid", body.razorpay_payment_id
    receipt = Receipt(payment_id=body.razorpay_payment_id, case_id=None, amount_paise=inv.amount_paise, emailed_to=cust.email)
    db.add(receipt)
    from app.agent.audit import append_audit
    await append_audit(db, case_id=None, actor="razorpay", action="payment_captured", reason_code="emailed_link",
                       channel="payment", simulated=False,
                       compliance_checks={"payment_id": body.razorpay_payment_id, "amount_paise": inv.amount_paise})
    await db.commit()
    return {"ok": True, "receipt_id": receipt.id, "already": False}
