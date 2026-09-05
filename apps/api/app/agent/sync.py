"""Fast payment sync — a finance app must reflect captures within seconds.

Every SYNC_INTERVAL (default 10s) the engine polls Razorpay for payment attempts on
every pending/failed invoice of real merchants with live keys, and runs the SAME
capture service a webhook would. Webhooks remain the instant path; this makes the
app self-healing without them (hosted links, missed deliveries, key rotation).
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.state_machine import capture_payment, open_case, advance_case
from app.core.logging import get_logger
from app.integrations import razorpay_client
import httpx

from app.agent.audit import append_audit
from app.models.base import Customer, Invoice, Merchant
from app.models.recovery import RecoveryCase, Receipt
from app.models.settings import load_creds

log = get_logger("agent.sync")

# Orders that failed verification (e.g. created under rotated-away keys) back off
# exponentially instead of being retried every tick.
_retry_at: dict[str, float] = {}


def _should_skip(order_id: str, now_ts: float) -> bool:
    return _retry_at.get(order_id, 0) > now_ts


def _backoff(order_id: str, now_ts: float) -> None:
    prev = _retry_at.get(order_id, now_ts)
    _retry_at[order_id] = min(prev + 3600, now_ts + 60 * (2 ** min(5, len(_retry_at))))  # capped backoff


async def sync_pending_invoices(db: AsyncSession, base_url: str = "http://localhost:3000") -> dict[str, Any]:
    out: dict[str, Any] = {"checked": 0, "captured": 0, "failed_detected": 0, "errors": 0}
    invoices = (await db.execute(select(Invoice).where(Invoice.status.in_(("pending", "failed")),
                                                      Invoice.razorpay_order_id.is_not(None)))).scalars().all()
    for inv in invoices:
        cust = await db.get(Customer, inv.customer_id)
        if cust is None or cust.email.endswith("@example.test"):
            continue  # synthetic cohort never touches the payment API
        creds = await load_creds(db, cust.merchant_id)
        if not creds.razorpay_ready or inv.razorpay_order_id.startswith("order_local"):
            continue
        import time as _time

        _now = _time.time()
        if _should_skip(inv.razorpay_order_id, _now):
            continue
        payments = await razorpay_client.fetch_order_payments(inv.razorpay_order_id, creds)
        if payments is None:
            out["errors"] += 1
            _backoff(inv.razorpay_order_id, _now)
            continue
        out["checked"] += 1
        captured = next((p for p in payments if p["status"] == "captured"), None)
        failed = next((p for p in payments if p["status"] == "failed" and p.get("error_code")), None)

        if captured and inv.status != "paid":
            case = (await db.execute(select(RecoveryCase).where(RecoveryCase.invoice_id == inv.id)
                                     .order_by(RecoveryCase.updated_at.desc()).limit(1))).scalars().first()
            if case and case.status != "recovered":
                await capture_payment(db, case, captured["id"], captured.get("amount") or inv.amount_paise,
                                      source="autosync:payment_captured")
            else:
                existing = (await db.execute(select(Receipt).where(Receipt.payment_id == captured["id"]))).scalars().first()
                if not existing:
                    inv.status, inv.razorpay_payment_id = "paid", captured["id"]
                    from app.agent.audit import append_audit

                    db.add(Receipt(payment_id=captured["id"], case_id=None, amount_paise=inv.amount_paise, emailed_to=cust.email))
                    await append_audit(db, case_id=None, actor="razorpay", action="payment_captured",
                                       reason_code="autosync:payment_request", channel="payment", simulated=False,
                                       compliance_checks={"payment_id": captured["id"], "amount_paise": inv.amount_paise})
            out["captured"] += 1
        elif failed and inv.status == "pending":
            existing = (await db.execute(select(RecoveryCase).where(RecoveryCase.invoice_id == inv.id,
                                                                   RecoveryCase.status.in_(("open", "escalated"))))).scalars().first()
            if not existing:
                inv.status = "failed"
                case = await open_case(db, cust, inv, "payment_failed",
                                       failed.get("error_code") or "payment_failed", actor="razorpay")
                await advance_case(db, case, base_url, actor="agent")
                out["failed_detected"] += 1
    await db.commit()
    if out["captured"] or out["failed_detected"]:
        log.info("sync.updated", **out)
    return out


async def reconcile_captures(db: AsyncSession) -> dict[str, int]:
    """Reconciliation: import captured payments that map to NO invoice we know about
    (dashboard-created links, orders under rotated keys, manual collections).
    Every captured rupee must appear in the ledger — nothing stays invisible.

    Match order: (1) known order → settle that invoice; (2) amount match → link a
    pending real invoice; (3) otherwise import as a direct payment record.
    """
    out = {"settled": 0, "linked": 0, "imported": 0, "skipped": 0}
    merchant = (await db.execute(select(Merchant))).scalars().first()
    if merchant is None:
        return out
    creds = await load_creds(db, merchant.id)
    if not creds.razorpay_ready:
        return out
    try:
        async with httpx.AsyncClient(timeout=15) as cl:
            r = await cl.get("https://api.razorpay.com/v1/payments?count=50",
                             auth=(creds.rzp_key_id, creds.rzp_key_secret))
        items = r.json().get("items", []) if r.status_code == 200 else []
    except Exception as e:
        log.warning("reconcile.fetch_failed", error=str(e)[:120])
        return out

    for p in items:
        if p.get("status") != "captured":
            continue
        pid, oid, amount = p["id"], p.get("order_id"), p.get("amount") or 0
        already = (await db.execute(select(Receipt).where(Receipt.payment_id == pid))).scalars().first()
        if already is not None:
            out["skipped"] += 1
            continue

        # (1) our order?
        inv = None
        if oid:
            inv = (await db.execute(select(Invoice).where(Invoice.razorpay_order_id == oid)
                                    .order_by(Invoice.created_at.desc()).limit(1))).scalars().first()
        if inv is not None:
            if inv.status != "paid":
                inv.status, inv.razorpay_payment_id = "paid", pid
                db.add(Receipt(payment_id=pid, case_id=None, amount_paise=amount, emailed_to=""))
                await append_audit(db, case_id=None, actor="razorpay", action="payment_captured",
                                   reason_code="reconcile:known_order", channel="payment", simulated=False,
                                   compliance_checks={"payment_id": pid, "amount_paise": amount})
                out["settled"] += 1
            continue

        # (2) amount match to a pending real invoice?
        cand = (await db.execute(select(Invoice).join(Customer, Invoice.customer_id == Customer.id)
                                 .where(Invoice.status.in_(("pending", "failed")), Invoice.amount_paise == amount,
                                        ~Customer.email.like("%@example.test"))
                                 .order_by(Invoice.created_at.asc()).limit(1))).scalars().first()
        if cand is not None:
            cand.status, cand.razorpay_payment_id = "paid", pid
            cand.razorpay_order_id = oid or cand.razorpay_order_id
            db.add(Receipt(payment_id=pid, case_id=None, amount_paise=amount, emailed_to=""))
            await append_audit(db, case_id=None, actor="razorpay", action="payment_captured",
                               reason_code="reconcile:amount_match", channel="payment", simulated=False,
                               compliance_checks={"payment_id": pid, "amount_paise": amount, "invoice": cand.id})
            out["linked"] += 1
            continue

        # (3) import as a direct payment
        email = (p.get("email") or "").lower()
        if not email or email.endswith("@example.test"):
            email = f"direct.{pid[-10:]}@payments.razorpay"
        cust = (await db.execute(select(Customer).where(Customer.email == email))).scalars().first()
        if cust is None:
            cust = Customer(merchant_id=merchant.id, name=p.get("name") or "Direct payer", email=email,
                            phone=p.get("contact") or "+910000000000", preferred_language="en-IN",
                            consent_email=False, is_demo_contact=True)
            db.add(cust)
            await db.flush()
        inv = Invoice(customer_id=cust.id, amount_paise=amount, due_date=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
                      status="paid", billing_cycle="one_time", title="Direct payment (imported from Razorpay)",
                      razorpay_order_id=oid, razorpay_payment_id=pid)
        db.add(inv)
        await db.flush()
        db.add(Receipt(payment_id=pid, case_id=None, amount_paise=amount, emailed_to=cust.email if "@" in cust.email and "payments.razorpay" not in cust.email else ""))
        await append_audit(db, case_id=None, actor="razorpay", action="payment_captured",
                           reason_code="reconcile:direct_import", channel="payment", simulated=False,
                           compliance_checks={"payment_id": pid, "amount_paise": amount, "payer": email[:3] + "***"})
        out["imported"] += 1
    await db.commit()
    if out["settled"] + out["linked"] + out["imported"]:
        log.info("reconcile.imported", **out)
    return out
