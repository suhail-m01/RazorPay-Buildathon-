"""Seed everything: merchant users, products, live demo contacts (from scripts/demo_contacts.py
or DEMO_CONTACTS_JSON env), ~92 synthetic cases with 90 days of history, playbooks."""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.agent.audit import append_audit  # noqa: E402
from app.core.logging import get_logger  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.base import Customer, Invoice, Merchant, MerchantUser, Product, Subscription  # noqa: E402
from app.models.recovery import OutboxMessage, Playbook, PromiseToPay, Receipt, RecoveryCase  # noqa: E402

log = get_logger("seed")

DEMO_USERS = [{"name": "Anjali Mehra", "email": "anjali@kirana.cloud", "role": "admin"},
              {"name": "Rohit Verma", "email": "rohit@kirana.cloud", "role": "recovery_agent"}]
MERCHANT_NAME = "Kirana Cloud Technologies"

PLAYBOOKS = [
    {"key": "SOFT_DECLINE_RETRY", "name": "Soft-decline timed retry", "traffic_share": 30,
     "definition": {"trigger": "payment.failed", "condition": "root_cause == soft_decline", "action": "retry_payment after 48h, then email link", "limits": {"max_attempts": 3}}},
    {"key": "DROPOFF_NUDGE", "name": "Checkout drop-off nudge", "traffic_share": 25,
     "definition": {"trigger": "checkout.abandoned", "condition": "amount >= 500", "action": "whatsapp 1-tap UPI link", "limits": {"max_attempts": 2}}},
    {"key": "MANDATE_REAUTH", "name": "Mandate re-authentication", "traffic_share": 20,
     "definition": {"trigger": "subscription.charged.failed", "condition": "mandate failure", "action": "email re-auth link + call after 72h", "limits": {"quiet_hours": "21:00-09:00 IST"}}},
    {"key": "B2B_AP_FOLLOWUP", "name": "B2B AP follow-up", "traffic_share": 15,
     "definition": {"trigger": "invoice.overdue", "condition": "net15/net30", "action": "email → escalation to human", "limits": {"discount_cap_pct": 5}}},
    {"key": "PROMISE_HOLD", "name": "Promise hold (≤7d)", "traffic_share": 10,
     "definition": {"trigger": "customer reply", "condition": "days 1-7", "action": "pause all channels until promised date 09:00 IST", "limits": {"cap_days": 7}}},
]


def _dt(days_ago: float) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days_ago)


async def _seed_case(db: AsyncSession, seq: int, merchant_id: str, row: dict[str, Any], live: bool) -> None:
    customer = Customer(merchant_id=merchant_id, name=row["name"], email=row["email"], phone=row["phone"],
                        preferred_language=row.get("language", "en-IN"), preferred_channel=row.get("preferred_channel", "email"),
                        consent_email=True, consent_sms=row.get("consents", {}).get("sms", False),
                        consent_whatsapp=row.get("consents", {}).get("whatsapp", False),
                        opted_out=row.get("opted_out", False), is_demo_contact=live)
    db.add(customer)
    await db.flush()
    product, price, cycle = row.get("product", "RecoverPay POS Pro"), row.get("amount_paise", 249900), row.get("billing_cycle", "monthly")
    prod = (await db.execute(select(Product).where(Product.name == product))).scalar_one_or_none()
    invoice = Invoice(customer_id=customer.id, amount_paise=price, due_date=_dt(row["created_days_ago"] + 3),
                      status={"recovered": "paid", "open": "overdue", "escalated": "overdue"}.get(row["status"], "overdue"))
    db.add(invoice)
    await db.flush()
    case = RecoveryCase(seq=seq, customer_id=customer.id, invoice_id=invoice.id, type=row["case_type"],
                        amount_paise=price, failure_reason_code=row.get("failure_code"),
                        risk_score=row.get("risk_score", 30),
                        root_cause={"payment_failed": "soft_decline", "checkout_abandoned": "voluntary_dropoff",
                                    "subscription_failed": "mandate_failure", "mandate_failed": "mandate_failure",
                                    "invoice_overdue": "b2b_nonpayment"}.get(row["case_type"], "soft_decline"),
                        confidence=0.82, current_stage=row["stage"], recovery_channel={"email_sent": "email", "whatsapp_sent": "whatsapp", "promise_wait": "email", "recovered": "email"}.get(row["stage"]),
                        attempts_count=row.get("attempts", 0), status=row["status"],
                        created_at=_dt(row["created_days_ago"]), updated_at=_dt(max(0.1, row["created_days_ago"] - 1)))
    if row["status"] == "recovered":
        case.recovered_at = _dt(row.get("recovered_days_ago") or 5)
    db.add(case)
    await db.flush()
    await append_audit(db, case_id=case.id, actor="agent", action="case_detected", reason_code=row["case_type"],
                       channel="system", created_at=_dt(row["created_days_ago"]), commit=False)
    await append_audit(db, case_id=case.id, actor="ai", action="diagnose", reason_code=case.root_cause,
                       channel="system", compliance_checks={"confidence": 0.82, "engine": "rules"},
                       created_at=_dt(row["created_days_ago"] - 0.01), commit=False)
    channel = {"email_sent": "email", "whatsapp_sent": "whatsapp"}.get(row["stage"], "email")
    if row["stage"] in ("email_sent", "whatsapp_sent", "promise_wait", "recovered", "escalated"):
        await append_audit(db, case_id=case.id, actor="agent", action=f"send_{channel}" if channel in ("email", "whatsapp") else "send_email",
                           channel=channel, simulated=not live, message_sent="[reminder with 1-tap payment link]",
                           compliance_checks={"policy": "pass", "quiet_hours_checked": True, "consent_checked": True},
                           created_at=_dt(max(0.05, row["created_days_ago"] - 0.5)), commit=False)
        db.add(OutboxMessage(channel=channel, recipient=customer.email if channel == "email" else customer.phone,
                             subject="Payment pending", body="[reminder with 1-tap payment link]",
                             status="simulated" if not live else "sent", simulated=not live, case_id=case.id,
                             created_at=_dt(max(0.05, row["created_days_ago"] - 0.5))))
    if row["stage"] == "promise_wait":
        db.add(PromiseToPay(case_id=case.id, promised_date=_dt(-3), promised_amount_paise=price,
                            utterance="3 din baad payment kar dunga", status="pending", created_at=_dt(1)))
    if row["status"] == "recovered":
        db.add(Receipt(payment_id=f"pay_seed{seq:05d}", case_id=case.id, amount_paise=price, created_at=case.recovered_at))


async def run_seed(db: AsyncSession, merchant_id: str | None = None) -> int:
    merchant = (await db.execute(select(Merchant).where(Merchant.name == MERCHANT_NAME))).scalar_one_or_none()
    if not merchant:
        merchant = Merchant(name=MERCHANT_NAME, gstin="29AABCK1234M1Z8")
        db.add(merchant)
        await db.flush()
    for u in DEMO_USERS:
        if not (await db.execute(select(MerchantUser).where(MerchantUser.email == u["email"]))).scalar_one_or_none():
            db.add(MerchantUser(merchant_id=merchant.id, email=u["email"], name=u["name"],
                                password_hash=hash_password("Punah@123"), role=u["role"]))
    for name, price, cycle in [("RecoverPay POS Pro", 249900, "monthly"), ("RecoverPay Analytics", 499900, "monthly"),
                               ("RecoverPay Inventory Sync", 129900, "monthly"), ("Storefront Builder Pack", 850000, "installment"),
                               ("Onboarding & Migration Pack", 1250000, "installment")]:
        if not (await db.execute(select(Product).where(Product.name == name))).scalar_one_or_none():
            db.add(Product(name=name, price_paise=price, billing_cycle=cycle))
    for p in PLAYBOOKS:
        if not (await db.execute(select(Playbook).where(Playbook.key == p["key"]))).scalar_one_or_none():
            db.add(Playbook(**p))
    await db.flush()

    # Base install: users + playbooks + products; plus the demo dataset so both
    # dashboards show meaningful records (products, amounts, history) out of the box.
    await db.commit()
    try:
        from seed_demo import seed_demo

        demo_n = await seed_demo(db, merchant.id)
    except Exception as e:  # never block an install on demo data
        demo_n = 0
        log.warning("seed.demo_skipped", error=str(e)[:120])
    log.info("seed.done", users=len(DEMO_USERS), playbooks=len(PLAYBOOKS), demo=demo_n)
    return demo_n


async def main() -> None:
    from app.core.db import SessionLocal, init_db

    await init_db()
    async with SessionLocal() as db:
        n = await run_seed(db)
    print(f"✓ seeded {n} cases (live demo contacts first, then synthetic bulk)")


if __name__ == "__main__":
    asyncio.run(main())
