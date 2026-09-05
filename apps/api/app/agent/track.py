"""Track: the reply engine — email hooks, portal reply box, date picker and ops-logged
call outcomes all funnel through this ONE path. Parser may use the LLM; the ≤7-day
ruling, STOP handling and dispute routing are pure code."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import act, templates
from app.agent.audit import append_audit
from app.agent.parser import apply_promise_rules, parse_reply
from app.agent.state_machine import new_promise_date
from app.core.logging import get_logger
from app.models.base import Customer
from app.models.recovery import PromiseToPay, RecoveryCase

log = get_logger("agent.track")


async def submit_reply(db: AsyncSession, case: RecoveryCase, text: str, actor: str,
                       base_url: str, source: str = "portal") -> dict[str, Any]:
    customer = await db.get(Customer, case.customer_id)
    lang = customer.preferred_language
    first = customer.name.split(" ")[0]
    pay_url = f"{base_url.rstrip('/')}/portal"  # portal session carries the deep context

    if case.status == "recovered":
        return {"intent": "unknown", "case_status": "recovered", "reply_subject": "Already settled",
                "reply_body": "This account is already fully settled — thank you!"}

    from app.models.settings import load_creds as _lc

    _creds = await _lc(db, customer.merchant_id)
    parsed = await parse_reply(text, gemini_key=_creds.gemini_api_key if customer.is_demo_contact else None)
    await append_audit(db, case_id=case.id, actor="customer", action="customer_reply",
                       reason_code=f"parsed_{parsed.intent}", channel=source, simulated=False,
                       message_sent=text[:300],
                       compliance_checks={"intent": parsed.intent, "days": parsed.days, "engine": parsed.engine}, commit=False)

    if parsed.intent == "stop":
        customer.opted_out = True
        case.status, case.current_stage, case.stop_reason = "stopped", "stopped", "customer_opted_out"
        await append_audit(db, case_id=case.id, actor="agent", action="stop_contact_enforced",
                           reason_code="customer_opted_out", simulated=False, commit=False)
        subject, body = templates.reply_message("stop", lang, first, pay_url)
        await act.tool_send_email(db, case, customer, subject, body)
        await db.commit()
        return {"intent": "stop", "case_status": "stopped", "reply_subject": subject, "reply_body": body}

    if parsed.intent == "dispute":
        case.status, case.current_stage = "escalated", "escalated"
        await act.tool_escalate_to_human(db, case, "review_dispute", f"Customer disputes: {text[:200]}")
        subject, body = templates.reply_message("dispute", lang, first, pay_url)
        await act.tool_send_email(db, case, customer, subject, body)
        await db.commit()
        return {"intent": "dispute", "case_status": "escalated", "reply_subject": subject, "reply_body": body}

    if parsed.intent == "paid":
        await append_audit(db, case_id=case.id, actor="agent", action="paid_claim_unmatched",
                           reason_code="no_capture_matched", simulated=False, message_sent=text[:200], commit=False)
        subject, body = templates.reply_message("paid", lang, first, pay_url)
        await act.tool_send_email(db, case, customer, subject, body)
        await db.commit()
        return {"intent": "paid", "case_status": case.status, "reply_subject": subject, "reply_body": body}

    if parsed.intent == "promise":
        ok, days, reject = apply_promise_rules(parsed)
        if ok and days:
            promised = new_promise_date(days)
            p = await act.tool_mark_promise(db, case, promised, days, text, parsed.amount_paise)
            case.current_stage, case.status = "promise_wait", "open"
            await append_audit(db, case_id=case.id, actor="agent", action="reminders_paused",
                               reason_code=f"promise_hold_{days}d", simulated=False,
                               compliance_checks={"resume_at": "09:00 IST", "promised_date": promised.date().isoformat()}, commit=False)
            subject, body = templates.reply_message("confirm", lang, first, pay_url, date=promised.strftime("%d %b"))
            await act.tool_send_email(db, case, customer, subject, body)
            await db.commit()
            return {"intent": "promise", "accepted": True, "days": days, "case_status": case.status,
                    "reply_subject": subject, "reply_body": body, "promise_id": p.id}
        # >7 days or vague → refuse (code, not the LLM)
        db.add(PromiseToPay(case_id=case.id, promised_date=datetime.now(timezone.utc), status="rejected",
                            reject_reason=reject, utterance=text[:500]))
        await append_audit(db, case_id=case.id, actor="agent", action="promise_rejected",
                           reason_code=reject, simulated=False, message_sent=text[:200], commit=False)
        subject, body = templates.reply_message("reject", lang, first, pay_url)
        await act.tool_send_email(db, case, customer, subject, body)
        await db.commit()
        return {"intent": "promise", "accepted": False, "reject_reason": reject, "case_status": case.status,
                "reply_subject": subject, "reply_body": body}

    subject, body = templates.reply_message("unknown", lang, first, pay_url)
    await act.tool_send_email(db, case, customer, subject, body)
    await db.commit()
    return {"intent": "unknown", "case_status": case.status, "reply_subject": subject, "reply_body": body}
