"""Customer portal: account login/register, dues, pay (Razorpay order), reply, opt-out."""
from __future__ import annotations

from typing import Any

from datetime import datetime, timezone  # noqa: E402
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agent.state_machine import capture_payment
from app.agent.decide import aware
from app.agent.track import submit_reply
from app.core.db import get_db
from app.core.deps import PORTAL_COOKIE, client_ip, get_portal_customer
from app.core.ratelimit import rate_limit
from app.core.logging import get_logger
from app.core.security import create_access_token, create_portal_token, hash_password, verify_password
from app.integrations import razorpay_client
from app.models.base import Customer, PortalAccount
from app.models.recovery import Invoice, PromiseToPay, RecoveryCase
from app.schemas import CheckoutIn, OrderIn, PortalLogin, PortalRegister, ReplyIn

log = get_logger("api.portal")
router = APIRouter(prefix="/portal", tags=["portal"])

def _issue(response: Response, account: PortalAccount) -> dict:
    """CHIPS cookie + signed-token body fallback (x-rp-portal) for cookie-less iframes."""
    token = create_portal_token(account.id)
    response.headers.append(
        "Set-Cookie",
        f"{PORTAL_COOKIE}={token}; Path=/; Max-Age={7 * 24 * 3600}; HttpOnly; SameSite=None; Secure; Partitioned",
    )
    return {"ok": True, "name": account.customer.name if account.customer else account.email,
            "redirect": "/portal", "portal_token": token}


@router.post("/register")
async def portal_register(body: PortalRegister, response: Response, db: AsyncSession = Depends(get_db)):
    email = body.email.lower()
    if await db.scalar(select(PortalAccount).where(PortalAccount.email == email)):
        raise HTTPException(409, "This email already has an account — please log in.")
    customer = (await db.execute(select(Customer).where(Customer.email == email))).scalars().first()
    if not customer:
        merchant_id = (await db.execute(select(Customer).limit(1))).scalar_one_or_none()
        customer = Customer(merchant_id=getattr(merchant_id, "merchant_id", "mch_default") if merchant_id else "mch_default",
                            name=body.name, email=email, phone=body.phone, is_demo_contact="example.test" not in email)
        db.add(customer)
        await db.flush()
    account = PortalAccount(customer_id=customer.id, email=email, password_hash=hash_password(body.password))
    db.add(account)
    await db.commit()
    await db.refresh(account, ["customer"])
    return _issue(response, account)


@router.post("/login")
async def portal_login(body: PortalLogin, response: Response, request: Request, db: AsyncSession = Depends(get_db)):
    if not await rate_limit(f"portal-login:{await client_ip(request)}", 10, 60):
        raise HTTPException(429, "Too many attempts — wait a minute.")
    email = body.email.lower()
    account = (await db.execute(select(PortalAccount).where(PortalAccount.email == email))).scalar_one_or_none()
    if not account or not verify_password(body.password, account.password_hash):
        raise HTTPException(401, "Wrong email or password.")
    await db.refresh(account, ["customer"])
    return _issue(response, account)


@router.post("/logout")
async def portal_logout(response: Response):
    response.delete_cookie(PORTAL_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
async def portal_me(customer: Customer = Depends(get_portal_customer), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    cases = (await db.execute(select(RecoveryCase).where(RecoveryCase.customer_id == customer.id)
                              .options(selectinload(RecoveryCase.invoice), selectinload(RecoveryCase.promises))
                              .order_by(RecoveryCase.updated_at.desc()))).scalars().unique().all()
    open_case = next((c for c in cases if c.status in ("open", "escalated")), None)
    promise = next((p for c in cases for p in c.promises if p.status == "pending"), None)
    invoices = (await db.execute(select(Invoice).where(Invoice.customer_id == customer.id).order_by(Invoice.due_date.desc()).limit(12))).scalars().all()
    # What the customer owes RIGHT NOW: an open recovery case first, otherwise every
    # unpaid payment request (pending/failed invoice). The portal must never show ₹0
    # while money is outstanding.
    unpaid = [i for i in invoices if i.status in ("pending", "failed")]
    if open_case is not None:
        due = {"kind": "case", "id": open_case.id, "seq": open_case.seq, "amount_paise": open_case.amount_paise,
               "due_date": open_case.invoice.due_date.isoformat() if open_case.invoice else None,
               "root_cause": open_case.root_cause,
               "title": (open_case.invoice.title if open_case.invoice else None) or "your invoice",
               "pending_requests": len([i for i in unpaid if i.id != open_case.invoice_id])}
    elif unpaid:
        due = {"kind": "request", "id": unpaid[0].id, "amount_paise": sum(i.amount_paise for i in unpaid),
               "due_date": max(i.due_date for i in unpaid).isoformat(), "root_cause": None,
               "title": unpaid[0].title or "payment request",
               "pending_requests": len(unpaid)}
    else:
        due = None
    return {
        "ok": True,
        "due": due,
        "customer": {"name": customer.name, "email": customer.email, "language": customer.preferred_language, "opted_out": customer.opted_out},
        "open_case": None if not open_case else {"id": open_case.id, "seq": open_case.seq, "amount_paise": open_case.amount_paise,
                                                 "stage": open_case.current_stage, "status": open_case.status,
                                                 "root_cause": open_case.root_cause, "due_date": open_case.invoice.due_date.isoformat()},
        "promise": None if not promise else {"promised_date": promise.promised_date.isoformat(), "status": promise.status},
        "history": [{"invoice": i.id, "amount_paise": i.amount_paise, "status": i.status, "due_date": i.due_date.isoformat(),
                     "payment_id": i.razorpay_payment_id, "title": i.title or "Payment request",
                     "billing_cycle": i.billing_cycle} for i in invoices],
        "cases": [{"id": c.id, "seq": c.seq, "status": c.status, "amount_paise": c.amount_paise} for c in cases[:10]],
    }


@router.post("/order")
async def create_order(body: OrderIn, customer: Customer = Depends(get_portal_customer), db: AsyncSession = Depends(get_db)) -> dict:
    """One order path for both situations: an open recovery case, or a pending payment request."""
    from app.models.settings import load_creds as _lc

    creds = await _lc(db, customer.merchant_id)

    # A specific pending payment (per-row Pay button in the portal)
    if body.invoice_id:
        inv = await db.get(Invoice, body.invoice_id)
        if not inv or inv.customer_id != customer.id:
            raise HTTPException(403, "Not your invoice.")
        if inv.status not in ("pending", "failed"):
            raise HTTPException(400, "This payment is already settled.")
        order = await razorpay_client.create_order(inv.amount_paise, f"rpr-{inv.id[-8:]}",
                                                   notes={"invoice_id": inv.id, "email": customer.email}, creds=creds)
        inv.razorpay_order_id = order["order_id"]
        await db.commit()
        return {"ok": True, "order_id": order["order_id"], "amount_paise": inv.amount_paise,
                "key_id": order["key_id"], "provider": order["provider"], "checkout_live": creds.razorpay_ready}

    case_stmt = select(RecoveryCase).where(RecoveryCase.customer_id == customer.id)
    if body.case_id:
        case_stmt = case_stmt.where(RecoveryCase.id == body.case_id)
    else:
        case_stmt = case_stmt.where(RecoveryCase.status.in_(("open", "escalated")))
    case = (await db.execute(case_stmt.order_by(RecoveryCase.updated_at.desc()).limit(1))).scalar_one_or_none()

    if case:
        amount = body.amount_paise or case.amount_paise
        if amount > case.amount_paise or amount < max(100, case.amount_paise // 10):
            raise HTTPException(400, "Partial payments must be between 10% and the full amount.")
        order = await razorpay_client.create_order(amount, f"rp-case-{case.seq}", notes={"case_id": case.id, "email": customer.email}, creds=creds)
        invoice = await db.get(Invoice, case.invoice_id)
        invoice.razorpay_order_id = order["order_id"]
        await db.commit()
        return {"ok": True, "order_id": order["order_id"], "amount_paise": amount, "key_id": order["key_id"],
                "provider": order["provider"], "checkout_live": creds.razorpay_ready}

    # No open case → pay a pending payment request directly.
    invoice = (await db.execute(select(Invoice).where(Invoice.customer_id == customer.id,
                                                     Invoice.status.in_(("pending", "failed")),
                                                     Invoice.razorpay_order_id.is_not(None))
                                .order_by(Invoice.created_at.asc()).limit(1))).scalar_one_or_none()
    if not invoice:
        raise HTTPException(404, "No open payment for your account.")
    amount = body.amount_paise or invoice.amount_paise
    if amount > invoice.amount_paise or amount < max(100, invoice.amount_paise // 10):
        raise HTTPException(400, "Partial payments must be between 10% and the full amount.")
    order = await razorpay_client.create_order(amount, f"rpr-{invoice.id[-8:]}", notes={"invoice_id": invoice.id, "email": customer.email}, creds=creds)
    invoice.razorpay_order_id = order["order_id"]
    await db.commit()
    return {"ok": True, "order_id": order["order_id"], "amount_paise": amount, "key_id": order["key_id"],
            "provider": order["provider"], "checkout_live": creds.razorpay_ready}


@router.post("/checkout")
async def checkout(body: CheckoutIn, customer: Customer = Depends(get_portal_customer), db: AsyncSession = Depends(get_db)) -> dict:
    """Hosted-Checkout signature verify OR the in-app test-mode capture (same code path).
    Works for recovery cases and direct payment requests alike."""
    from datetime import datetime as _dt

    from app.agent.audit import append_audit as _audit
    from app.models.settings import load_creds as _lc

    invoice = (await db.execute(select(Invoice).where(Invoice.razorpay_order_id == body.order_id).order_by(Invoice.created_at.desc()).limit(1))).scalars().first()
    if not invoice or invoice.customer_id != customer.id:
        raise HTTPException(403, "Not your order.")
    creds = await _lc(db, customer.merchant_id)

    if creds.razorpay_ready and body.payment_id and body.signature:
        if not razorpay_client.verify_checkout_signature(body.order_id, body.payment_id, body.signature, creds):
            raise HTTPException(400, "Signature verification failed.")
        payment_id = body.payment_id
    elif creds.razorpay_ready and not body.test_fallback:
        raise HTTPException(400, "Signature verification failed.")
    else:
        payment_id = body.payment_id or razorpay_client.local_payment_id()

    case = (await db.execute(select(RecoveryCase).where(RecoveryCase.invoice_id == invoice.id)
                             .order_by(RecoveryCase.updated_at.desc()).limit(1))).scalar_one_or_none()
    if case:
        res = await capture_payment(db, case, payment_id, invoice.amount_paise, source="checkout")
        return {"ok": True, **res}

    # Direct payment request (no recovery case): settle the invoice + receipt.
    from app.models.recovery import Receipt

    existing = (await db.execute(select(Receipt).where(Receipt.payment_id == payment_id))).scalar_one_or_none()
    if not existing:
        invoice.status, invoice.razorpay_payment_id = "paid", payment_id
        receipt = Receipt(payment_id=payment_id, case_id=None, amount_paise=invoice.amount_paise, emailed_to=customer.email)
        db.add(receipt)
        await _audit(db, case_id=None, actor="razorpay" if creds.razorpay_ready else "system",
                     action="payment_captured", reason_code="payment_request", channel="payment",
                     simulated=not creds.razorpay_ready,
                     compliance_checks={"payment_id": payment_id, "amount_paise": invoice.amount_paise}, commit=True)
        return {"ok": True, "receipt_id": receipt.id, "already": False}
    return {"ok": True, "receipt_id": existing.id, "already": True}


@router.post("/reply")
async def portal_reply(body: ReplyIn, request: Request, customer: Customer = Depends(get_portal_customer),
                       db: AsyncSession = Depends(get_db)) -> dict:
    case = (await db.execute(select(RecoveryCase).where(RecoveryCase.customer_id == customer.id,
                                                       RecoveryCase.status.in_(("open", "escalated")))
                             .order_by(RecoveryCase.updated_at.desc()).limit(1))).scalar_one_or_none()
    if not case:
        # No active recovery yet — if an unpaid request is past due, open a case (the same
        # rule the auto-detector uses) so promise-to-pay is always reachable from the portal.
        inv = (await db.execute(select(Invoice).where(Invoice.customer_id == customer.id,
                                                     Invoice.status.in_(("pending", "failed")))
                                .order_by(Invoice.created_at.desc()).limit(1))).scalar_one_or_none()
        if inv and (inv.status == "failed" or (aware(inv.due_date) or datetime.now(timezone.utc)) < datetime.now(timezone.utc)):
            from app.agent.state_machine import open_case as _oc

            case = await _oc(db, customer, inv, "invoice_overdue", "customer_reached_out", actor="agent")
            await db.commit()
        else:
            raise HTTPException(404, "Nothing is overdue right now — you can simply pay from this page.")
    return await submit_reply(db, case, body.text, f"customer:{customer.id}", str(request.base_url), source="portal")


@router.post("/optout")
async def portal_optout(customer: Customer = Depends(get_portal_customer), db: AsyncSession = Depends(get_db)) -> dict:
    customer.opted_out = True
    case = (await db.execute(select(RecoveryCase).where(RecoveryCase.customer_id == customer.id,
                                                       RecoveryCase.status.in_(("open", "escalated")))
                             .order_by(RecoveryCase.updated_at.desc()).limit(1))).scalar_one_or_none()
    if case:
        case.status, case.current_stage, case.stop_reason = "stopped", "stopped", "customer_opted_out"
    from app.agent.audit import append_audit
    await append_audit(db, case_id=case.id if case else None, actor="customer", action="opt_out",
                       reason_code="customer_opted_out", simulated=False, commit=True)
    return {"ok": True, "message": "You will not be contacted again."}


@router.post("/exchange")
async def exchange_magic_token(body: dict, response: Response, db: AsyncSession = Depends(get_db)) -> dict:
    """Swap a valid magic-link token for a portal session cookie."""
    import hashlib as _hl

    token = (body or {}).get("token", "")
    if not token:
        raise HTTPException(400, "Missing token")
    from app.core.deps import rate_limit as _rl
    if not await _rl(f"exchange:{token[:12]}", 10, 60):
        raise HTTPException(429, "Too many attempts")
    row = await db.get(PortalToken, _hl.sha256(token.encode()).hexdigest())
    if not row or row.revoked or row.expires_at.replace(tzinfo=None) < datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(404, "This link is no longer valid")
    account = (await db.execute(select(PortalAccount).where(PortalAccount.customer_id == row.customer_id))).scalar_one_or_none()
    if not account:
        raise HTTPException(404, "No portal account for this customer — register first")
    row.used_count += 1
    await db.commit()
    return _issue(response, account)
