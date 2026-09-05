"""Admin: seed management (re-seed / top-up), scheduler tick, playbooks."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.state_machine import advance_case, open_case, tick
from app.core.db import get_db, SessionLocal
from app.core.deps import get_current_user
from app.core.logging import get_logger
from app.models.base import Customer, MerchantUser
from app.models.recovery import AuditLog, OutboxMessage, Playbook, PromiseToPay, Receipt, RecoveryCase

log = get_logger("api.admin")
router = APIRouter(prefix="/admin", tags=["admin"])

FAILURES = ["insufficient_funds", "card_expired", "authentication_failed", "gateway_timeout", "dropoff_at_otp",
            "mandate_auth_expired", "e_mandate_revoked_by_bank", "net15_unpaid", "network_error"]


async def inject_case(db: AsyncSession, merchant_id: str, case_type: str, base_url: str) -> dict[str, Any]:
    """Create a synthetic signal and run the pipeline on it (gated send)."""
    n = (await db.execute(select(func.count(Customer.id)))).scalar() or 0
    if case_type == "random" or case_type not in ("payment_failed", "checkout_abandoned", "subscription_failed", "mandate_failed", "invoice_overdue"):
        case_type = ("payment_failed", "checkout_abandoned", "subscription_failed", "mandate_failed", "invoice_overdue")[n % 5]
    customer = Customer(merchant_id=merchant_id, name=f"Injected Signal {n + 1}",
                        email=f"inject.{secrets.token_hex(3)}.case@example.test", phone=f"+9199999{n:05d}",
                        preferred_language="en-IN", consent_email=True, consent_sms=True, consent_whatsapp=True,
                        is_demo_contact=False)
    db.add(customer)
    await db.flush()
    from app.models.base import Invoice
    invoice = Invoice(customer_id=customer.id, amount_paise=249900,
                      due_date=datetime.now(timezone.utc) - timedelta(days=3), status="overdue")
    db.add(invoice)
    await db.flush()
    case = await open_case(db, customer, invoice, case_type, FAILURES[n % len(FAILURES)], actor="human")
    await db.commit()
    res = await advance_case(db, case, base_url)
    return {"ok": True, "case_id": case.id, "seq": case.seq, "case_type": case_type, "result": res.get("status"),
            "note": "Synthetic contact — outbound is gate-simulated."}


@router.post("/tick")
async def run_tick(request: Request, db: AsyncSession = Depends(get_db), user: MerchantUser = Depends(get_current_user)):
    summary = await tick(db, str(request.base_url).replace(":8000", ":3000"))
    return {"ok": True, "summary": summary}


@router.post("/seed/reset")
async def seed_reset(db: AsyncSession = Depends(get_db), user: MerchantUser = Depends(get_current_user)) -> dict:
    """Wipe recovery data and re-seed synthetic + live-demo dataset (keeps merchant users)."""
    for table in (AuditLog, Receipt, PromiseToPay, OutboxMessage, RecoveryCase):
        await db.execute(delete(table))
    from app.models.base import Invoice, PortalAccount, PortalToken, Product, Subscription
    from app.models.recovery import HumanApprovalRequest, WebhookDelivery
    for table in (HumanApprovalRequest, PortalToken, WebhookDelivery, Invoice, Subscription, Product):
        await db.execute(delete(table))
    await db.execute(delete(Customer).where(Customer.is_demo_contact == False))  # noqa: E712 — keep live rows
    await db.commit()
    # Seed out-of-band so this request's session stays clean.
    async with SessionLocal() as seed_db:
        import sys
        sys.path.insert(0, "/home/user/recoverpay/scripts")
        from seed_all import run_seed
        count = await run_seed(seed_db, merchant_id=user.merchant_id)
    return {"ok": True, "seeded": count}


@router.post("/seed/topup")
async def seed_topup(request: Request, count: int = 10, db: AsyncSession = Depends(get_db),
                     user: MerchantUser = Depends(get_current_user)) -> dict:
    made = 0
    for _ in range(max(1, min(count, 50))):
        res = await inject_case(db, user.merchant_id, "random", str(request.base_url).replace(":8000", ":3000"))
        made += 1
    return {"ok": True, "injected": made}


@router.get("/playbooks")
async def playbooks(db: AsyncSession = Depends(get_db), user: MerchantUser = Depends(get_current_user)) -> dict:
    rows = (await db.execute(select(Playbook).order_by(Playbook.traffic_share.desc()))).scalars().all()
    return {"ok": True, "playbooks": [{"key": p.key, "name": p.name, "version": p.version, "status": p.status,
                                       "traffic_share": p.traffic_share, "definition": p.definition} for p in rows]}


@router.get("/backups")
async def backups_list(user: MerchantUser = Depends(get_current_user)):
    from app.core.backup import list_backups

    return {"ok": True, "backups": list_backups()}


@router.post("/backups/restore")
async def backups_restore(body: dict, user: MerchantUser = Depends(get_current_user)):
    from app.core.backup import restore_tag

    tag = (body or {}).get("tag", "")
    res = restore_tag(tag)
    return res
