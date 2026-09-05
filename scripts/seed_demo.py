"""Demo dataset — populates dashboards with realistic records: product names, amounts,
paid history with receipts, pending requests and worked recovery cases.

Contacts are synthetic (@example.test, send-gated); money movements are labelled
demo in the audit compliance checks. Safe to run on an existing DB (top-up) —
it never touches real customers or invoices.
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))

from faker import Faker  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

from app.agent.audit import append_audit  # noqa: E402
from app.core.db import SessionLocal, init_db  # noqa: E402
from app.core.logging import get_logger  # noqa: E402
from app.models.base import Customer, Invoice, Merchant  # noqa: E402
from app.models.recovery import Receipt, RecoveryCase  # noqa: E402

log = get_logger("seed.demo")
fake = Faker("en_IN")
Faker.seed(7)

CATALOG = [
    {"title": "RecoverPay POS Pro — monthly plan", "amount": 249900, "cycle": "monthly"},
    {"title": "RecoverPay Analytics — yearly plan", "amount": 499900, "cycle": "yearly"},
    {"title": "Inventory Sync — monthly plan", "amount": 129900, "cycle": "monthly"},
    {"title": "Storefront Builder — one-time setup", "amount": 850000, "cycle": "one_time"},
    {"title": "Onboarding & Migration — one-time", "amount": 1250000, "cycle": "one_time"},
    {"title": "Voice Add-on — monthly plan", "amount": 99900, "cycle": "monthly"},
]
LANGS = ["en-IN", "hi-IN", "hi-IN", "ta-IN", "te-IN", "mr-IN"]
FAIL_CODES = {"payment_failed": "insufficient_funds", "checkout_abandoned": "dropoff_at_otp",
              "mandate_failed": "e_mandate_revoked_by_bank", "invoice_overdue": "net15_unpaid"}
ROOTS = {"payment_failed": "soft_decline", "checkout_abandoned": "voluntary_dropoff",
         "mandate_failed": "mandate_failure", "invoice_overdue": "b2b_nonpayment"}


def dt(days_ago: float) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days_ago)


async def seed_demo(db, merchant_id: str, count: int = 12, force: bool = False) -> int:
    if not force:
        titled = (await db.execute(select(func.count(Invoice.id)).where(Invoice.title.is_not(None)))).scalar() or 0
        if titled > 0:
            return 0  # already topped up
    seq = (await db.execute(select(func.max(RecoveryCase.seq)))).scalar() or 1000
    made = 0
    for i in range(count):
        name = fake.name()
        cust = Customer(
            merchant_id=merchant_id, name=name,
            email=f"{name.lower().replace(' ', '.').replace('.', '')}{i}@example.test",
            phone=f"+9199999{fake.random_int(10000, 99999):05d}"[:14],
            preferred_language=LANGS[i % len(LANGS)], preferred_channel="email",
            consent_email=True, consent_sms=i % 3 != 0, consent_whatsapp=i % 2 == 0,
            is_demo_contact=False,  # synthetic: all sends gate-simulated
        )
        db.add(cust)
        await db.flush()
        product = CATALOG[i % len(CATALOG)]
        roll = i % 6
        # roll → 0,1: paid  |  2,3: pending  |  4: recovered case  |  5: open case
        status = "paid" if roll in (0, 1) else "pending" if roll in (2, 3) else "failed"
        inv = Invoice(customer_id=cust.id, amount_paise=product["amount"],
                      due_date=dt(30 - i), status=status, billing_cycle=product["cycle"],
                      title=product["title"], created_at=dt(32 - i))
        if status == "paid":
            inv.razorpay_payment_id = f"pay_demo{i:04d}"
        db.add(inv)
        await db.flush()
        if roll in (4, 5):
            ctype = list(FAIL_CODES)[i % 4]
            seq += 1
            case = RecoveryCase(seq=seq, customer_id=cust.id, invoice_id=inv.id, type=ctype,
                                amount_paise=product["amount"], failure_reason_code=FAIL_CODES[ctype],
                                risk_score=45 + (i * 5) % 50, root_cause=ROOTS[ctype], confidence=0.85,
                                current_stage="email_sent", recovery_channel="email",
                                attempts_count=0, status="open", created_at=dt(28 - i))
            if roll == 4:  # recovered
                case.status, case.current_stage, case.recovered_at = "recovered", "recovered", dt(20 - i)
            db.add(case)
            await db.flush()
            if roll == 4:
                db.add(Receipt(payment_id=f"pay_demo_rc{i:04d}", case_id=case.id,
                               amount_paise=product["amount"], created_at=dt(20 - i)))
            await append_audit(db, case_id=case.id, actor="agent", action="case_detected",
                               reason_code=ctype, channel="system", simulated=True,
                               compliance_checks={"demo": True}, created_at=dt(28 - i), commit=False)
            await append_audit(db, case_id=case.id, actor="ai", action="diagnose",
                               reason_code=ROOTS[ctype], channel="system", simulated=True,
                               compliance_checks={"confidence": 0.85, "demo": True},
                               created_at=dt(28 - i) + timedelta(hours=1), commit=False)
            await append_audit(db, case_id=case.id, actor="agent", action="send_email",
                               channel="email", simulated=True, message_sent="[reminder with payment link]",
                               compliance_checks={"policy": "pass", "demo": True},
                               created_at=dt(27 - i), commit=False)
            if roll == 4:
                await append_audit(db, case_id=case.id, actor="system", action="payment_captured",
                                   channel="payment", simulated=True,
                                   compliance_checks={"demo": True}, created_at=dt(20 - i), commit=False)
        made += 1
    await db.commit()
    log.info("demo.seeded", customers=made)
    return made


async def main() -> None:
    await init_db()
    async with SessionLocal() as db:
        merchant = (await db.execute(select(Merchant))).scalars().first()
        n = await seed_demo(db, merchant.id)
        print(f"✓ demo dataset: {n} new demo customers (top-up; existing data untouched)" if n
              else "✓ demo dataset already present")


if __name__ == "__main__":
    asyncio.run(main())
