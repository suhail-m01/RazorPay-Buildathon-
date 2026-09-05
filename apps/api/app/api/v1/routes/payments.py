"""Real payment operations: add customers, create payment requests (real Razorpay order +
real email with the link), and sync order status from Razorpay (real failure detection)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import secrets as _secrets_mod
from app.agent.audit import append_audit
from app.agent import templates
from app.agent.state_machine import advance_case, capture_payment, open_case
from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.logging import get_logger
from app.integrations import email_client, razorpay_client
from app.models.base import Customer, Invoice, Merchant, MerchantUser
from app.models.recovery import RecoveryCase
from app.models.settings import load_creds

log = get_logger("api.payments")
router = APIRouter(tags=["payments"])


class CustomerIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str = Field(min_length=8, max_length=16)
    preferred_language: str = "en-IN"
    billing_cycle: str | None = Field(default=None, pattern="^(monthly|yearly|one_time)$")


class RequestIn(BaseModel):
    customer_id: str
    amount_paise: int = Field(gt=99)
    title: str = Field(min_length=2, max_length=120)
    note: str | None = None
    billing_cycle: str = Field(default="one_time", pattern="^(monthly|yearly|one_time)$")
    channels: list[Literal["email", "whatsapp", "voice"]] = Field(default_factory=lambda: ["email"], min_length=1)
    whatsapp_permission: bool = False
    voice_permission: bool = False


def order_probe_reason(link: dict) -> str | None:
    return link.get("error")


def _base(request: Request) -> str:
    """Public base for links that leave the system (email/WhatsApp). Behind the preview
    proxy the browser host is in x-forwarded-host; localhost fallback for dev."""
    host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
    proto = request.headers.get("x-forwarded-proto") or ("https" if "e2b.app" in host else "http")
    if host:
        return f"{proto}://{host}"
    return str(request.base_url).replace(":8000", ":3000").rstrip("/")


async def _merchant_customer(db: AsyncSession, user: MerchantUser, customer_id: str) -> Customer:
    cust = await db.get(Customer, customer_id)
    if not cust or cust.merchant_id != user.merchant_id:
        raise HTTPException(404, "Customer not found")
    return cust


# ------------------------------------------------------------------ customers
@router.post("/customers")
async def create_customer(body: CustomerIn, db: AsyncSession = Depends(get_db),
                          user: MerchantUser = Depends(get_current_user)):
    email = body.email.lower()
    existing = (await db.execute(select(Customer).where(Customer.merchant_id == user.merchant_id,
                                                       Customer.email == email))).scalars().first()
    if existing:
        # Returning customer: refresh their record with whatever is new in the payload.
        existing.name = body.name or existing.name
        existing.phone = body.phone or existing.phone
        if body.billing_cycle:
            existing.billing_cycle = body.billing_cycle
        await db.commit()
        return {"ok": True, "customer_id": existing.id, "existing": True, "billing_cycle": existing.billing_cycle}
    cust = Customer(merchant_id=user.merchant_id, name=body.name, email=email, phone=body.phone,
                    preferred_language=body.preferred_language if body.preferred_language in
                    ("en-IN", "hi-IN", "ta-IN", "te-IN", "mr-IN") else "en-IN",
                    billing_cycle=body.billing_cycle,
                    consent_email=True, is_demo_contact=False)  # merchant-created contact is dispatchable; seeded demo contacts remain protected
    db.add(cust)
    await db.commit()
    return {"ok": True, "customer_id": cust.id, "existing": False, "billing_cycle": cust.billing_cycle}


@router.get("/customers")
async def list_customers(db: AsyncSession = Depends(get_db), user: MerchantUser = Depends(get_current_user)):
    rows = (await db.execute(select(Customer).where(Customer.merchant_id == user.merchant_id)
                             .order_by(Customer.created_at.desc()).limit(1000))).scalars().all()
    return {"ok": True, "customers": [{"id": c.id, "name": c.name, "email": c.email, "phone": c.phone,
                                       "language": c.preferred_language, "billing_cycle": c.billing_cycle,
                                       "created_at": c.created_at.isoformat()} for c in rows]}


# ------------------------------------------------------------------ payment requests
@router.post("/payment-requests")
async def create_payment_request(body: RequestIn, request: Request, db: AsyncSession = Depends(get_db),
                                 user: MerchantUser = Depends(get_current_user)) -> dict[str, Any]:
    cust = await _merchant_customer(db, user, body.customer_id)
    creds = await load_creds(db, user.merchant_id)
    if creds.razorpay_ready and body.amount_paise > 50_000_000:
        raise HTTPException(400, "₹{:,.0f} exceeds Razorpay's per-transaction limit of ₹5,00,000 — split it into multiple requests".format(body.amount_paise / 100))
    cust.billing_cycle = body.billing_cycle  # latest arrangement defines their plan
    invoice = Invoice(customer_id=cust.id, amount_paise=body.amount_paise,
                      due_date=datetime.now(timezone.utc), status="pending",
                      billing_cycle=body.billing_cycle, title=body.title)
    db.add(invoice)
    await db.flush()
    if creds.razorpay_ready and body.amount_paise > 50_000_000:
        raise HTTPException(400, "₹{:,.0f} exceeds Razorpay's per-transaction limit of ₹5,00,000".format(body.amount_paise / 100))
    link = await razorpay_client.create_payment_link(
        amount_paise=body.amount_paise, receipt=f"rpr-{invoice.id[-8:]}-{_secrets_mod.token_hex(3)}", base_url=_base(request),
        customer={"name": cust.name, "email": cust.email, "contact": cust.phone}, creds=creds)
    if creds.razorpay_ready and link.get("error"):
        # ORDER creation failed at Razorpay — a real problem; never email a dead link.
        raise HTTPException(502, f"Razorpay rejected this order: {link['error']}")
    # Note: hosted rzp.io links are capped at 30 per test account. When the quota is
    # exhausted we email OUR pay page, which opens the real Razorpay Checkout on the
    # same order — identical security, unlimited usage.
    invoice.razorpay_order_id = link["order_id"]
    invoice.razorpay_link_id = link.get("link_id")
    rupees = body.amount_paise / 100
    # Channel plan is explicit and visible to the merchant. Email is the default;
    # WhatsApp and Voice use the same Twilio credentials configured in Settings.
    channels = list(dict.fromkeys(body.channels))
    # Preflight selected live channels before dispatch. A selected Twilio channel
    # must be configured, otherwise the merchant gets a clear error instead of a
    # false-looking "sent" request.
    if "whatsapp" in channels and not creds.whatsapp_ready:
        raise HTTPException(400, "WhatsApp is selected but no WhatsApp provider is fully configured in Settings")
    if "voice" in channels and not creds.voice_ready:
        raise HTTPException(400, "Phone call is selected but Twilio Voice is not fully configured in Settings")
    if "whatsapp" in channels and body.whatsapp_permission:
        cust.consent_whatsapp = True
    if "whatsapp" in channels and not cust.consent_whatsapp:
        raise HTTPException(400, "WhatsApp selected but customer WhatsApp permission is not recorded")
    if "voice" in channels and not body.voice_permission:
        raise HTTPException(400, "Phone call selected — confirm that you have permission to call this customer")

    delivery: dict[str, Any] = {}
    message_body = (
        f"Hi {cust.name.split(' ')[0]},\n\n{body.note + chr(10) + chr(10) if body.note else ''}"
        f"Please complete your payment of ₹{rupees:,.0f} for “{body.title}”:\n\n{link['url']}\n\n"
        f"Secure checkout by Razorpay. If anything failed, this link also lets you retry.\n\n— RecoverPay AI"
    )

    if "email" in channels:
        delivered, provider = await email_client.send_email(
            cust.email, f"Payment request — ₹{rupees:,.0f}: {body.title}", message_body, creds)
        delivery["email"] = {"ok": delivered, "provider": provider, "queued": not creds.email_ready}
        await append_audit(db, case_id=None, actor=f"human:{user.name}", action="payment_request_sent",
                           channel="email", simulated=not delivered,
                           compliance_checks={"order_id": link["order_id"], "provider": link["provider"],
                                              "email_provider": provider, "amount_paise": body.amount_paise})

    if "whatsapp" in channels:
        from app.integrations.messaging import send_whatsapp
        delivered, provider = await send_whatsapp(cust.phone, message_body, creds=creds)
        delivery["whatsapp"] = {"ok": delivered, "provider": provider}
        await append_audit(db, case_id=None, actor=f"human:{user.name}", action="payment_request_sent",
                           channel="whatsapp", simulated=not delivered,
                           compliance_checks={"order_id": link["order_id"], "provider": provider, "amount_paise": body.amount_paise})

    if "voice" in channels:
        from app.integrations.voice import place_call
        merchant = await db.get(Merchant, user.merchant_id)
        voice_script = templates.voice_script(cust.preferred_language, cust.name, merchant.name if merchant else "your merchant",
                                               body.title, body.amount_paise,
                                               datetime.now(timezone.utc).strftime("%d %b %Y"), link["url"])
        delivered, provider, call_sid = await place_call(cust.phone, voice_script, cust.preferred_language, creds=creds)
        delivery["voice"] = {"ok": delivered, "provider": provider, "call_sid": call_sid}
        await append_audit(db, case_id=None, actor=f"human:{user.name}", action="payment_request_sent",
                           channel="voice", simulated=not delivered,
                           compliance_checks={"order_id": link["order_id"], "provider": provider, "call_sid": call_sid,
                                              "amount_paise": body.amount_paise})

    await db.commit()
    from app.core.backup import make_backup as _mb
    _mb()
    return {"ok": True, "invoice_id": invoice.id, "order_id": link["order_id"], "link": link["url"],
            "provider": link["provider"], "delivery": delivery,
            "email_delivered": bool(delivery.get("email", {}).get("ok")),
            "email_provider": delivery.get("email", {}).get("provider"),
            "email_queued": bool(delivery.get("email", {}).get("queued"))}


@router.get("/payment-requests")
async def list_requests(db: AsyncSession = Depends(get_db), user: MerchantUser = Depends(get_current_user)):
    rows = (await db.execute(
        select(Invoice, Customer).join(Customer, Invoice.customer_id == Customer.id)
        .where(Customer.merchant_id == user.merchant_id).order_by(Invoice.created_at.desc()).limit(50))).all()
    out = []
    for inv, cust in rows:
        if not inv.razorpay_order_id:
            continue
        case = (await db.execute(select(RecoveryCase).where(RecoveryCase.invoice_id == inv.id)
                                 .order_by(RecoveryCase.updated_at.desc()).limit(1))).scalar_one_or_none()
        out.append({"invoice_id": inv.id, "order_id": inv.razorpay_order_id, "amount_paise": inv.amount_paise,
                    "status": inv.status, "customer": cust.name, "email": cust.email,
                    "title": inv.title or "Payment request",
                    "billing_cycle": inv.billing_cycle or cust.billing_cycle or "one_time",
                    "customer_cycle": cust.billing_cycle,
                    "created_at": inv.created_at.isoformat(), "case_seq": case.seq if case else None,
                    "case_id": case.id if case else None})
    return {"ok": True, "requests": out}


@router.post("/payments/sync-all")
async def sync_all(request: Request, db: AsyncSession = Depends(get_db),
                   user: MerchantUser = Depends(get_current_user)) -> dict[str, Any]:
    """Pull the latest payment state from Razorpay for every pending invoice (real merchants)."""
    from app.agent.sync import reconcile_captures, sync_pending_invoices

    out = await sync_pending_invoices(db, _base(request))
    out["reconciled"] = await reconcile_captures(db)
    return {"ok": True, **out}


# ------------------------------------------------------------------ status sync (real failure/capture detection)
@router.post("/payments/{order_id}/sync")
async def sync_order(order_id: str, request: Request, db: AsyncSession = Depends(get_db),
                     user: MerchantUser = Depends(get_current_user)) -> dict[str, Any]:
    invoice = (await db.execute(select(Invoice).where(Invoice.razorpay_order_id == order_id).order_by(Invoice.created_at.desc()).limit(1))).scalars().first()
    if not invoice:
        raise HTTPException(404, "Unknown order")
    cust = await db.get(Customer, invoice.customer_id)
    if cust.merchant_id != user.merchant_id:
        raise HTTPException(403, "Not your order")
    creds = await load_creds(db, user.merchant_id)
    payments = await razorpay_client.fetch_order_payments(order_id, creds)
    if payments is None:
        return {"ok": True, "synced": False, "message": "Sync needs live Razorpay keys (or the payment link checkout)."}

    captured = next((p for p in payments if p["status"] == "captured"), None)
    failed = next((p for p in payments if p["status"] == "failed"), None)

    if captured:
        case = (await db.execute(select(RecoveryCase).where(RecoveryCase.invoice_id == invoice.id)
                                 .order_by(RecoveryCase.updated_at.desc()).limit(1))).scalar_one_or_none()
        if case and case.status != "recovered":
            await capture_payment(db, case, captured["id"], captured.get("amount") or invoice.amount_paise,
                                  source="sync:payment_captured")
        else:
            invoice.status, invoice.razorpay_payment_id = "paid", captured["id"]
            await db.commit()
        return {"ok": True, "synced": True, "result": "captured", "payment_id": captured["id"]}

    if failed and invoice.status != "paid":
        existing = (await db.execute(select(RecoveryCase).where(RecoveryCase.invoice_id == invoice.id,
                                                               RecoveryCase.status.in_(("open", "escalated"))))).scalar_one_or_none()
        if not existing:
            invoice.status = "failed"
            case = await open_case(db, cust, invoice, "payment_failed",
                                   failed.get("error_code") or failed.get("error_description") or "payment_failed",
                                   actor="razorpay")
            await db.commit()
            res = await advance_case(db, case, _base(request), actor="agent")
            return {"ok": True, "synced": True, "result": "failed_case_opened", "case_seq": case.seq,
                    "agent": res.get("status"), "error_code": failed.get("error_code")}
        return {"ok": True, "synced": True, "result": "already_in_recovery"}

    return {"ok": True, "synced": True, "result": f"no_change_{invoice.status}",
            "attempts": len(payments)}
