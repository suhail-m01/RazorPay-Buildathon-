"""Bounded Act toolbelt. Fixed set of actions; every send passes the policy layer AND the
is_demo_contact hard gate inside the lowest-level channel functions — synthetic contacts
can never trigger real dispatch regardless of the calling path."""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.audit import append_audit
from app.agent.decide import evaluate_policy
from app.core.logging import get_logger
from app.integrations import email_client, messaging, razorpay_client  # messaging = sms_whatsapp
from app.models.base import Customer
from app.models.recovery import AuditLog, OutboxMessage, PromiseToPay, RecoveryCase
from app.models.settings import load_creds

log = get_logger("agent.act")

TOOLBELT = ["send_email", "send_sms", "send_whatsapp", "place_voice_call", "create_payment_link",
            "retry_payment", "mark_promise_to_pay", "escalate_to_human", "close_case"]


async def _gate_and_send(db: AsyncSession, case: RecoveryCase, customer: Customer, proposed: str,
                         channel: str, recipient: str, subject: str | None, body: str) -> dict[str, Any]:
    """Policy gate → channel dispatch (with the demo-contact hard gate inside) → audit."""
    decision = evaluate_policy(case, customer, None, proposed)
    if not decision.allowed:
        await append_audit(db, case_id=case.id, actor="agent", action=f"{proposed}_blocked",
                           reason_code=decision.reason_code, channel=channel, message_sent=body[:400],
                           simulated=True, compliance_checks=decision.checks, commit=False)
        return {"ok": False, "blocked": decision.reason_code, "checks": decision.checks}

    # HARD GATE: synthetic contacts never dispatch — enforced here, at the lowest level.
    simulated = not customer.is_demo_contact
    row = OutboxMessage(channel=channel, recipient=recipient, subject=subject, body=body,
                        case_id=case.id, simulated=simulated, status="queued")
    db.add(row)
    await db.flush()

    delivered, provider = False, "simulated"
    if simulated:
        row.status = "simulated"
    else:
        try:
            if channel == "email":
                creds = await load_creds(db, getattr(customer, "merchant_id", None))
                delivered, provider = await email_client.send_email(recipient, subject or "", body, creds)
            elif channel == "sms":
                _c = await load_creds(db, getattr(customer, "merchant_id", None))
                delivered, provider = await messaging.send_sms(recipient, body, creds=_c)
            elif channel == "whatsapp":
                _c = await load_creds(db, getattr(customer, "merchant_id", None))
                delivered, provider = await messaging.send_whatsapp(recipient, body, creds=_c)
            row.status = "sent" if delivered else "failed"
            row.provider = provider
        except Exception as e:  # a channel failure must never break the ladder
            log.error("act.channel_error", channel=channel, error=str(e))
            row.status, row.provider = "failed", "error"

    await append_audit(db, case_id=case.id, actor="agent", action=proposed, reason_code="policy_pass",
                       channel=channel, message_sent=body[:400], simulated=simulated,
                       compliance_checks={**(decision.checks or {}), "delivered": delivered, "provider": provider},
                       commit=False)
    return {"ok": True, "simulated": simulated, "delivered": delivered, "outbox_id": row.id,
            "status": row.status, "checks": decision.checks}


async def tool_send_email(db: AsyncSession, case: RecoveryCase, customer: Customer, subject: str, body: str) -> dict[str, Any]:
    return await _gate_and_send(db, case, customer, "send_email", "email", customer.email, subject, body)


async def tool_send_sms(db: AsyncSession, case: RecoveryCase, customer: Customer, body: str) -> dict[str, Any]:
    return await _gate_and_send(db, case, customer, "send_sms", "sms", customer.phone, None, body)


async def tool_send_whatsapp(db: AsyncSession, case: RecoveryCase, customer: Customer, body: str) -> dict[str, Any]:
    return await _gate_and_send(db, case, customer, "send_whatsapp", "whatsapp", customer.phone, None, body)


async def tool_create_payment_link(db: AsyncSession, case: RecoveryCase, customer: Customer, base_url: str) -> dict[str, Any]:
    creds = await load_creds(db, getattr(customer, "merchant_id", None))
    if not customer.is_demo_contact:
        creds = None  # synthetic contacts never touch the payment API — local orders only
    link = await razorpay_client.create_payment_link(
        amount_paise=case.amount_paise, receipt=f"rp-case-{case.seq}", base_url=base_url,
        customer={"name": customer.name, "email": customer.email, "contact": customer.phone}, creds=creds,
    )
    # Pin the order to the invoice so the pay page / status sync can always find it.
    from app.models.base import Invoice as _Invoice

    invoice = await db.get(_Invoice, case.invoice_id)
    if invoice is not None:
        invoice.razorpay_order_id = link["order_id"]
        invoice.razorpay_link_id = link.get("link_id")
        await db.flush()
    await append_audit(db, case_id=case.id, actor="agent", action="create_payment_link",
                       reason_code="policy_pass", channel="payment", simulated=not razorpay_client.is_live(),
                       message_sent=link["url"], compliance_checks={"provider": link["provider"]}, commit=False)
    return link


async def tool_mark_promise(db: AsyncSession, case: RecoveryCase, promised_date, days: int,
                            utterance: str, amount_paise: int | None = None) -> PromiseToPay:
    p = PromiseToPay(case_id=case.id, promised_date=promised_date, promised_amount_paise=amount_paise or case.amount_paise,
                     utterance=utterance[:500], status="pending")
    db.add(p)
    await db.flush()
    await append_audit(db, case_id=case.id, actor="agent", action="mark_promise_to_pay",
                       reason_code=f"hold_{days}d_within_cap", simulated=False,
                       message_sent=utterance[:200], commit=False)
    return p


async def tool_escalate_to_human(db: AsyncSession, case: RecoveryCase, suggested: str, reason: str, reviewer_id: str | None = None):
    from app.models.recovery import HumanApprovalRequest

    req = HumanApprovalRequest(case_id=case.id, suggested_action=suggested, reason=reason[:500])
    db.add(req)
    case.status, case.current_stage, case.stop_reason = "escalated", "escalated", "needs_human"
    await db.flush()
    await append_audit(db, case_id=case.id, actor="agent", action="escalate_to_human",
                       reason_code=suggested, simulated=False, message_sent=reason[:300], commit=False)
    return req


async def tool_close_case(db: AsyncSession, case: RecoveryCase, reason: str, actor: str = "agent") -> None:
    case.status = "closed"
    case.stop_reason = reason[:48]
    await append_audit(db, case_id=case.id, actor=actor, action="close_case",
                       reason_code=reason[:48], simulated=False, commit=False)


async def tool_place_voice_call(db: AsyncSession, case: RecoveryCase, customer: Customer,
                                script: str, ssml: str) -> dict[str, Any]:
    """Policy-gated real Twilio Voice call for live/demo contacts.
    Synthetic contacts never reach Twilio. The provider result is audited.
    """
    decision = evaluate_policy(case, customer, None, "place_voice_call")
    if not decision.allowed:
        await append_audit(db, case_id=case.id, actor="agent", action="place_voice_call_blocked",
                           reason_code=decision.reason_code, channel="voice", simulated=True,
                           message_sent=script[:300], compliance_checks=decision.checks, commit=False)
        return {"ok": False, "blocked": decision.reason_code}

    simulated = not customer.is_demo_contact
    row = OutboxMessage(channel="voice", recipient=customer.phone, subject=None, body=script,
                        case_id=case.id, simulated=simulated, status="simulated" if simulated else "queued")
    db.add(row)
    await db.flush()

    delivered, provider, call_sid = False, "simulated", None
    if not simulated:
        try:
            from app.integrations import voice
            creds = await load_creds(db, getattr(customer, "merchant_id", None))
            delivered, provider, call_sid = await voice.place_call(
                customer.phone, script, customer.preferred_language, creds=creds)
            row.status = "sent" if delivered else ("queued" if provider == "queued" else "failed")
            row.provider, row.provider_id = provider, call_sid
        except Exception as e:
            log.error("act.voice_error", error=str(e))
            row.status, row.provider = "failed", "error"
    await append_audit(db, case_id=case.id, actor="agent", action="place_voice_call",
                       reason_code="policy_pass", channel="voice", simulated=simulated,
                       message_sent=script[:400],
                       compliance_checks={**(decision.checks or {}), "delivered": delivered,
                                          "provider": provider, "call_sid": call_sid,
                                          "ssml_chars": len(ssml), "language": customer.preferred_language}, commit=False)
    return {"ok": delivered or simulated, "simulated": simulated, "delivered": delivered,
            "provider": provider, "call_sid": call_sid, "script": script, "outbox_id": row.id,
            "status": row.status, "checks": decision.checks}


async def tool_retry_payment(db: AsyncSession, case: RecoveryCase, customer: Customer,
                             base_url: str) -> dict[str, Any]:
    """Mandate/subscription retry sequencer: mints a FRESH order for the same amount so the
    charge/mandate can be re-attempted. Audited; capped by the same attempt policy."""
    decision = evaluate_policy(case, customer, None, "retry_payment")
    if not decision.allowed:
        await append_audit(db, case_id=case.id, actor="agent", action="retry_payment_blocked",
                           reason_code=decision.reason_code, channel="payment", simulated=True,
                           compliance_checks=decision.checks, commit=False)
        return {"ok": False, "blocked": decision.reason_code}

    prior = 0
    from sqlalchemy import select as _select

    rows = (await db.execute(_select(AuditLog).where(AuditLog.case_id == case.id, AuditLog.action == "retry_payment"))).scalars().all()
    prior = len(rows)
    creds = await load_creds(db, getattr(customer, "merchant_id", None))
    if not customer.is_demo_contact:
        creds = None  # synthetic contacts: local retry orders only
    order = await razorpay_client.create_order(case.amount_paise, f"rp-retry-{case.seq}-{prior + 1}",
                                               notes={"case_id": case.id, "retry": prior + 1}, creds=creds)
    from app.models.base import Invoice as _Invoice

    invoice = await db.get(_Invoice, case.invoice_id)
    if invoice is not None:
        invoice.razorpay_order_id = order["order_id"]
        await db.flush()
    await append_audit(db, case_id=case.id, actor="agent", action="retry_payment",
                       reason_code=f"attempt_{prior + 1}_scheduled", channel="payment",
                       simulated=not creds.razorpay_ready,
                       compliance_checks={**(decision.checks or {}), "order_id": order["order_id"],
                                          "provider": order["provider"]}, commit=False)
    return {"ok": True, "order_id": order["order_id"], "attempt": prior + 1, "provider": order["provider"]}
