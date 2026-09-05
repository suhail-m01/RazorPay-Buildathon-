"""Merchant case routes: queue, detail, advance, approvals, magic links, payment links, inject."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agent.audit import verify_chain
from app.agent.state_machine import advance_case, open_case
from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.logging import get_logger
from app.integrations import razorpay_client
from app.models.base import Customer, Invoice, MerchantUser, PortalAccount
from app.models.recovery import AuditLog, HumanApprovalRequest, PortalToken, PromiseToPay, RecoveryCase
from app.schemas import AdvanceIn, ApprovalIn

log = get_logger("api.cases")
router = APIRouter(prefix="/cases", tags=["cases"])


def base_url(request: Request) -> str:
    host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
    proto = request.headers.get("x-forwarded-proto") or ("https" if "e2b.app" in host else "http")
    if host and ":8000" not in host:
        return f"{proto}://{host}"
    return str(request.base_url).rstrip("/")


@router.get("")
async def case_queue(status: str | None = None, type: str | None = None, q: str | None = None,
                     min_risk: int | None = None, db: AsyncSession = Depends(get_db),
                     user: MerchantUser = Depends(get_current_user)) -> dict[str, Any]:
    stmt = select(RecoveryCase).options(selectinload(RecoveryCase.customer), selectinload(RecoveryCase.promises)).order_by(RecoveryCase.risk_score.desc(), RecoveryCase.updated_at.desc()).limit(300)
    if status:
        stmt = stmt.where(RecoveryCase.status == status)
    if type:
        stmt = stmt.where(RecoveryCase.type == type)
    if min_risk is not None:
        stmt = stmt.where(RecoveryCase.risk_score >= min_risk)
    rows = (await db.execute(stmt)).scalars().unique().all()
    inv_ids = [c.invoice_id for c in rows]
    inv_titles: dict[str, str] = {}
    if inv_ids:
        from app.models.base import Invoice as _Inv

        for inv in (await db.execute(select(_Inv).where(_Inv.id.in_(inv_ids)))).scalars():
            inv_titles[inv.id] = inv.title or "Payment"
    out = []
    for c in rows:
        cust = c.customer
        if q and q.lower() not in (cust.name + cust.email + cust.phone).lower():
            continue
        out.append({
            "id": c.id, "seq": c.seq, "customer": cust.name, "email": cust.email, "phone": cust.phone,
            "item": inv_titles.get(c.invoice_id, "Payment"),
            "is_demo_contact": cust.is_demo_contact, "type": c.type, "amount_paise": c.amount_paise,
            "risk_score": c.risk_score, "root_cause": c.root_cause, "confidence": c.confidence,
            "stage": c.current_stage, "status": c.status, "attempts": c.attempts_count,
            "promise_pending": any(p.status == "pending" for p in c.promises),
            "created_at": c.created_at.isoformat(), "updated_at": c.updated_at.isoformat(),
        })
    return {"ok": True, "count": len(out), "cases": out}


@router.get("/{case_id}")
async def case_detail(case_id: str, db: AsyncSession = Depends(get_db), user: MerchantUser = Depends(get_current_user)):
    c = await db.get(RecoveryCase, case_id, options=[selectinload(RecoveryCase.customer), selectinload(RecoveryCase.invoice)])
    if not c:
        raise HTTPException(404, "Case not found")
    audit = (await db.execute(select(AuditLog).where(AuditLog.case_id == case_id).order_by(AuditLog.id.desc()).limit(50))).scalars().all()
    from app.models.recovery import OutboxMessage as _Om

    voice_row = (await db.execute(select(_Om).where(_Om.case_id == case_id, _Om.channel == "voice")
                                  .order_by(_Om.id.desc()).limit(1))).scalar_one_or_none()
    promises = (await db.execute(select(PromiseToPay).where(PromiseToPay.case_id == case_id).order_by(PromiseToPay.id.desc()))).scalars().all()
    return {
        "ok": True,
        "case": {"id": c.id, "seq": c.seq, "type": c.type, "amount_paise": c.amount_paise, "risk_score": c.risk_score,
                 "root_cause": c.root_cause, "confidence": c.confidence, "stage": c.current_stage, "status": c.status,
                 "attempts": c.attempts_count, "failure_reason_code": c.failure_reason_code, "stop_reason": c.stop_reason,
                 "recovered_at": c.recovered_at.isoformat() if c.recovered_at else None, "created_at": c.created_at.isoformat()},
        "customer": {"name": c.customer.name, "email": c.customer.email, "phone": c.customer.phone,
                     "preferred_channel": c.customer.preferred_channel, "preferred_language": c.customer.preferred_language,
                     "consents": {"email": c.customer.consent_email, "sms": c.customer.consent_sms, "whatsapp": c.customer.consent_whatsapp},
                     "opted_out": c.customer.opted_out, "is_demo_contact": c.customer.is_demo_contact},
        "invoice": {"id": c.invoice.id, "amount_paise": c.invoice.amount_paise, "status": c.invoice.status,
                    "due_date": c.invoice.due_date.isoformat(), "order_id": c.invoice.razorpay_order_id,
                    "title": c.invoice.title or "Payment request", "billing_cycle": c.invoice.billing_cycle},
        "timeline": [{"id": a.id, "actor": a.actor, "action": a.action, "reason_code": a.reason_code, "channel": a.channel,
                      "message": (a.message_sent or "")[:400], "simulated": a.simulated, "checks": a.compliance_checks,
                      "ts": a.created_at.isoformat()} for a in audit],
        "promises": [{"id": p.id, "promised_date": p.promised_date.isoformat(), "days": None, "status": p.status,
                      "reject_reason": p.reject_reason, "utterance": p.utterance[:200], "created_at": p.created_at.isoformat()} for p in promises],
    }


@router.post("/{case_id}/advance")
async def case_advance(case_id: str, request: Request, _b: AdvanceIn | None = None,
                       db: AsyncSession = Depends(get_db), user: MerchantUser = Depends(get_current_user)):
    c = await db.get(RecoveryCase, case_id)
    if not c:
        raise HTTPException(404, "Case not found")
    res = await advance_case(db, c, base_url(request), actor=f"human:{user.name}")
    return {"ok": True, "seq": c.seq, **res}


@router.post("/{case_id}/magic-link")
async def magic_link(case_id: str, request: Request, db: AsyncSession = Depends(get_db),
                     user: MerchantUser = Depends(get_current_user)) -> dict:
    c = await db.get(RecoveryCase, case_id)
    if not c:
        raise HTTPException(404, "Case not found")
    token = secrets.token_hex(24)
    db.add(PortalToken(token_hash=hashlib.sha256(token.encode()).hexdigest(), case_id=c.id, customer_id=c.customer_id,
                       expires_at=datetime.now(timezone.utc) + timedelta(days=7)))
    await db.commit()
    return {"ok": True, "url": f"{base_url(request).replace(':8000', ':3000')}/p/{token}"}


@router.post("/{case_id}/payment-link")
async def payment_link(case_id: str, request: Request, db: AsyncSession = Depends(get_db),
                       user: MerchantUser = Depends(get_current_user)) -> dict:
    c = await db.get(RecoveryCase, case_id)
    if not c:
        raise HTTPException(404, "Case not found")
    cust = await db.get(Customer, c.customer_id)
    from app.agent import act
    link = await act.tool_create_payment_link(db, c, cust, base_url(request).replace(":8000", ":3000"))
    await db.commit()
    return {"ok": True, **link}


@router.post("/{case_id}/retry")
async def retry_payment(case_id: str, request: Request, db: AsyncSession = Depends(get_db),
                        user: MerchantUser = Depends(get_current_user)):
    """Mandate/subscription retry sequencer — manual trigger of the same tool the scheduler uses."""
    from app.agent import act

    c = await db.get(RecoveryCase, case_id)
    if not c:
        raise HTTPException(404, "Case not found")
    cust = await db.get(Customer, c.customer_id)
    res = await act.tool_retry_payment(db, c, cust, base_url(request))
    await db.commit()
    return {"ok": res.get("ok", False), **res}


@router.post("/{case_id}/reply-as")
async def reply_as_customer(case_id: str, body: dict, request: Request, db: AsyncSession = Depends(get_db),
                            user: MerchantUser = Depends(get_current_user)):
    """Run the exact customer-reply engine against a case (demo/testing from the console)."""
    from app.agent.track import submit_reply

    c = await db.get(RecoveryCase, case_id)
    if not c:
        raise HTTPException(404, "Case not found")
    text = (body or {}).get("text", "")
    if not text.strip():
        raise HTTPException(400, "Missing text")
    return await submit_reply(db, c, text.strip()[:1000], f"human:{user.name}", base_url(request), source="console")


@router.get("/approvals/list")
async def approvals_list(db: AsyncSession = Depends(get_db), user: MerchantUser = Depends(get_current_user)):
    rows = (await db.execute(select(HumanApprovalRequest).where(HumanApprovalRequest.status == "pending")
                             .order_by(HumanApprovalRequest.id.desc()).limit(100))).scalars().all()
    out = []
    for r in rows:
        c = await db.get(RecoveryCase, r.case_id)
        cust = await db.get(Customer, c.customer_id) if c else None
        out.append({"id": r.id, "case_id": r.case_id, "case_seq": c.seq if c else None, "customer": cust.name if cust else "?",
                    "amount_paise": c.amount_paise if c else 0, "is_demo_contact": cust.is_demo_contact if cust else False,
                    "suggested_action": r.suggested_action, "reason": r.reason, "created_at": r.created_at.isoformat()})
    return {"ok": True, "count": len(out), "approvals": out}


@router.post("/approvals/{approval_id}")
async def resolve_approval(approval_id: str, body: ApprovalIn, db: AsyncSession = Depends(get_db),
                           user: MerchantUser = Depends(get_current_user)):
    req = await db.get(HumanApprovalRequest, approval_id)
    if not req or req.status != "pending":
        raise HTTPException(404, "Approval not found or already resolved")
    req.status, req.reviewer_id, req.resolved_at = body.decision, user.id, datetime.now(timezone.utc)
    c = await db.get(RecoveryCase, req.case_id)
    if body.decision == "approved" and c:
        c.status, c.current_stage = "open", "diagnosed"  # resume ladder from email rung
    elif c and c.status != "recovered":
        c.status, c.current_stage, c.stop_reason = "closed", "closed", "human_closed"
    from app.agent.audit import append_audit
    await append_audit(db, case_id=req.case_id, actor="human", action=f"approval_{body.decision}",
                       reason_code=req.suggested_action, simulated=False, message_sent=body.reason, commit=True)
    return {"ok": True, "status": body.decision}


@router.get("/audit/list")
async def audit_list(page: int = 0, size: int = 60, db: AsyncSession = Depends(get_db),
                     user: MerchantUser = Depends(get_current_user)):
    rows = (await db.execute(select(AuditLog).order_by(AuditLog.id.desc()).offset(page * size).limit(size))).scalars().all()
    return {"ok": True, "count": len(rows), "logs": [{"id": r.id, "case_id": r.case_id, "actor": r.actor, "action": r.action,
             "reason_code": r.reason_code, "channel": r.channel, "message": (r.message_sent or "")[:300],
             "simulated": r.simulated, "hash": (r.hash or "")[:16], "created_at": r.created_at.isoformat()} for r in rows]}


@router.get("/audit/verify")
async def audit_verify(db: AsyncSession = Depends(get_db), user: MerchantUser = Depends(get_current_user)):
    return await verify_chain(db)
