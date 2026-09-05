"""The recovery FSM: Detect → Diagnose → Decide → Act → Track. One advance path used by
ops buttons, the scheduler tick and injected signals; one capture path for webhooks,
hosted Checkout and the in-app test checkout."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import act, templates
from app.agent.audit import append_audit
from app.agent.decide import MAX_OUTBOUND_AFTER_FIRST_EMAIL, aware, at_9am_ist, choose_primary_channel, compute_risk, days_between, ist_now
from app.agent.diagnose import diagnose
from app.agent.parser import ParsedReply
from app.core.logging import get_logger
from app.integrations import razorpay_client
from datetime import timedelta

from app.models.base import Customer, Invoice, Merchant
from app.models.recovery import AuditLog, OutboxMessage, PromiseToPay, Receipt, RecoveryCase

log = get_logger("agent.fsm")


async def next_seq(db: AsyncSession) -> int:
    n = (await db.execute(select(func.max(RecoveryCase.seq)))).scalar() or 1000
    return n + 1


# ---------------------------------------------------------------- Detect
async def open_case(db: AsyncSession, customer: Customer, invoice: Invoice, case_type: str,
                    failure_code: str | None, actor: str = "agent") -> RecoveryCase:
    case = RecoveryCase(
        seq=await next_seq(db), customer_id=customer.id, invoice_id=invoice.id, type=case_type,
        amount_paise=invoice.amount_paise, failure_reason_code=failure_code,
        risk_score=compute_risk(RecoveryCase(amount_paise=invoice.amount_paise, attempts_count=0), max(0, days_between(invoice.due_date, ist_now())), 0),
        current_stage="detected", status="open",
    )
    db.add(case)
    invoice.status = "failed" if case_type in ("payment_failed", "subscription_failed", "mandate_failed") else "overdue"
    await db.flush()
    await append_audit(db, case_id=case.id, actor=actor, action="case_detected", reason_code=case_type,
                       channel="system", simulated=False,
                       compliance_checks={"amount_paise": invoice.amount_paise, "failure_code": failure_code}, commit=False)
    return case


# ---------------------------------------------------------------- Diagnose
async def run_diagnosis(db: AsyncSession, case: RecoveryCase) -> dict[str, Any]:
    from app.models.settings import load_creds as _lc

    cust = await db.get(Customer, case.customer_id)
    _creds = await _lc(db, cust.merchant_id) if cust else None
    # LLM diagnosis for real contacts; the synthetic cohort uses the deterministic
    # taxonomy (same code path — no network calls inside batch loops).
    d = await diagnose(case.type, case.failure_reason_code, case.amount_paise,
                       gemini_key=_creds.gemini_api_key if _creds else None,
                       use_llm=bool(cust and cust.is_demo_contact))
    case.root_cause, case.confidence = d["root_cause"], d["confidence"]
    case.current_stage = "diagnosed"
    await db.flush()
    await append_audit(db, case_id=case.id, actor="ai" if d["engine"] == "llm" else "agent",
                       action="diagnose", reason_code=d["root_cause"], simulated=False,
                       compliance_checks={"confidence": d["confidence"], "engine": d["engine"],
                                          "notes": d["notes"][:160], "evidence": d.get("evidence", "")}, commit=False)
    return d


# ---------------------------------------------------------------- Decide+Act (one ladder rung)
async def advance_case(db: AsyncSession, case: RecoveryCase, base_url: str, actor: str = "agent") -> dict[str, Any]:
    customer = await db.get(Customer, case.customer_id)
    invoice = await db.get(Invoice, case.invoice_id)
    merchant = await db.get(Merchant, customer.merchant_id) if customer.merchant_id else None
    merchant_name = merchant.name if merchant else "us"
    item_name = "your subscription" if invoice and invoice.subscription_id else "your invoice"
    if case.status == "recovered":
        return {"status": "already_recovered"}

    if case.current_stage in ("detected", "diagnosed"):
        if case.current_stage == "detected":
            await run_diagnosis(db, case)
        link = await act.tool_create_payment_link(db, case, customer, base_url)
        chosen = choose_primary_channel(case, customer)

        if chosen == "voice":
            script = templates.voice_script(customer.preferred_language, customer.name, merchant_name,
                                            item_name, case.amount_paise, invoice.due_date.strftime("%d %b %Y"), link["url"])
            ssml = f"<speak><prosody rate='95%'>{script}</prosody></speak>"
            res = await act.tool_place_voice_call(db, case, customer, script, ssml)
            if res["ok"]:
                case.current_stage, case.recovery_channel = "voice_attempted", "voice"
                case.attempts_count += 1
            await db.commit()
            return {"status": res.get("blocked") or "voice_attempted", "channel": "voice", "simulated": res.get("simulated")}

        if chosen == "whatsapp":
            body = templates.whatsapp_message(customer.preferred_language, customer.name.split(" ")[0], merchant_name,
                                              item_name, case.amount_paise, invoice.due_date.strftime("%d %b %Y"), link["url"])
            res = await act.tool_send_whatsapp(db, case, customer, body)
            if res["ok"]:
                case.current_stage, case.recovery_channel = "whatsapp_sent", "whatsapp"
                case.attempts_count += 1
            await db.commit()
            return {"status": res.get("blocked") or "whatsapp_sent", "channel": "whatsapp", "simulated": res.get("simulated")}

        subject, body = templates.email_message(customer.preferred_language, customer.name.split(" ")[0],
                                                merchant_name, item_name,
                                                case.amount_paise, invoice.due_date.strftime("%d %b %Y"), link["url"])
        res = await act.tool_send_email(db, case, customer, subject, body)
        if res["ok"]:
            case.current_stage, case.recovery_channel = "email_sent", "email"
        await db.commit()
        return {"status": res.get("blocked") or "email_sent", "channel": "email", "simulated": res.get("simulated")}

    pending = (await db.execute(select(PromiseToPay).where(PromiseToPay.case_id == case.id, PromiseToPay.status == "pending"))).scalar_one_or_none()
    if pending and aware(pending.promised_date) > datetime.now(timezone.utc):
        return {"status": "paused_promise_hold", "until": pending.promised_date.isoformat()}

    if case.current_stage == "email_sent":
        link = await act.tool_create_payment_link(db, case, customer, base_url)
        body = templates.whatsapp_message(customer.preferred_language, customer.name.split(" ")[0], merchant_name,
                                          item_name, case.amount_paise, invoice.due_date.strftime("%d %b %Y"), link["url"])
        res = await act.tool_send_whatsapp(db, case, customer, body)
        if res["ok"]:
            case.current_stage, case.recovery_channel = "whatsapp_sent", "whatsapp"
            case.attempts_count += 1
        await db.commit()
        return {"status": res.get("blocked") or "whatsapp_sent", "simulated": res.get("simulated")}

    if case.current_stage == "whatsapp_sent":
        if case.attempts_count >= MAX_OUTBOUND_AFTER_FIRST_EMAIL:
            req = await act.tool_escalate_to_human(db, case, "escalate_to_human",
                                                   f"Attempt cap ({MAX_OUTBOUND_AFTER_FIRST_EMAIL}) reached with no recovery.")
            await db.commit()
            return {"status": "escalated", "approval_id": req.id}
        link_url = (await act.tool_create_payment_link(db, case, customer, base_url))["url"]
        script = templates.voice_script(customer.preferred_language, customer.name, merchant_name,
                                        item_name, case.amount_paise, invoice.due_date.strftime("%d %b %Y"), link_url)
        ssml = f"<speak><prosody rate='95%'>{script}</prosody></speak>"
        res = await act.tool_place_voice_call(db, case, customer, script, ssml)
        if res["ok"]:
            case.current_stage, case.recovery_channel = "voice_attempted", "voice"
            case.attempts_count += 1
        await db.commit()
        return {"status": res.get("blocked") or "voice_attempted", "channel": "voice", "simulated": res.get("simulated")}

    if case.current_stage == "voice_attempted":
        req = await act.tool_escalate_to_human(db, case, "escalate_to_human", "Ladder exhausted — human review required.")
        await db.commit()
        return {"status": "escalated", "approval_id": req.id}

    if case.current_stage == "sms_sent":
        # Hinglish voice rung (final outbound): script + SSML stored, console plays it back.
        link_url = (await act.tool_create_payment_link(db, case, customer, base_url))["url"]
        script = templates.voice_script(customer.preferred_language, customer.name, merchant_name,
                                        item_name, case.amount_paise, invoice.due_date.strftime("%d %b %Y"), link_url)
        ssml = f"<speak><prosody rate='95%'>{script}</prosody></speak>"
        res_voice = await act.tool_place_voice_call(db, case, customer, script, ssml)
        if res_voice["ok"]:
            case.current_stage, case.recovery_channel = "voice_attempted", "voice"
            case.attempts_count += 1
        await db.commit()
        return {"status": res_voice.get("blocked") or "voice_attempted", "simulated": res_voice.get("simulated")}

    return {"status": f"no_transition_from_{case.current_stage}"}


# ---------------------------------------------------------------- Capture (single payment-success path)
async def capture_payment(db: AsyncSession, case: RecoveryCase, payment_id: str, amount_paise: int,
                          source: str) -> dict[str, Any]:
    existing = (await db.execute(select(Receipt).where(Receipt.payment_id == payment_id))).scalar_one_or_none()
    if existing:
        return {"receipt_id": existing.id, "already": True}

    customer = await db.get(Customer, case.customer_id)
    invoice = await db.get(Invoice, case.invoice_id)
    now = datetime.now(timezone.utc)
    case.status, case.current_stage, case.recovered_at = "recovered", "recovered", now
    invoice.status, invoice.razorpay_payment_id = "paid", payment_id
    await db.execute(select(OutboxMessage).where(OutboxMessage.case_id == case.id, OutboxMessage.status.in_(("queued",))))
    receipt = Receipt(payment_id=payment_id, case_id=case.id, amount_paise=amount_paise,
                      emailed_to=customer.email if customer.is_demo_contact else f"{customer.email[:1]}***@{customer.email.split('@')[-1]}")
    db.add(receipt)
    await db.execute(select(PromiseToPay).where(PromiseToPay.case_id == case.id, PromiseToPay.status == "pending"))
    for p in (await db.execute(select(PromiseToPay).where(PromiseToPay.case_id == case.id, PromiseToPay.status == "pending"))).scalars():
        p.status = "kept"
    await append_audit(db, case_id=case.id, actor="razorpay" if source.startswith("webhook") else "system",
                       action="payment_captured", reason_code=source, channel="payment",
                       simulated=not razorpay_client.is_live(),
                       compliance_checks={"payment_id": payment_id, "amount_paise": amount_paise}, commit=False)

    # Receipt email (transactional) via the merchant's configured email channel.
    from app.integrations import email_client as _ec
    from app.models.settings import load_creds as _lc

    _creds = await _lc(db, customer.merchant_id)
    if _creds.email_ready and customer.is_demo_contact:
        _ok, _prov = await _ec.send_email(
            customer.email, f"Payment received — {payment_id}",
            f"Hi {customer.name.split(' ')[0]},\n\nWe received your payment of ₹{amount_paise/100:,.0f}.\n"
            f"Razorpay payment id: {payment_id}\n\nThank you!\n— RecoverPay AI", _creds)
        await append_audit(db, case_id=case.id, actor="system", action="receipt_emailed",
                           channel="email", simulated=not _ok,
                           compliance_checks={"to": customer.email[:3] + "***", "provider": _prov}, commit=False)
    await db.commit()
    # Money captured & committed — durability snapshot for real customers.
    if not customer.email.endswith("@example.test"):
        from app.core.backup import make_backup as _mb

        try:
            _mb()
        except Exception:
            pass
    return {"receipt_id": receipt.id, "case_seq": case.seq, "already": False}


# ---------------------------------------------------------------- Tick (scheduler / cron entry)
async def tick(db: AsyncSession, base_url: str) -> dict[str, Any]:
    out = {"promises_broken": 0, "advanced": 0, "escalated": 0, "dropoff_detected": 0,
           "overdue_detected": 0, "mandate_retries": 0, "details": {}}
    now = datetime.now(timezone.utc)

    # 0a) AUTO-DETECT checkout drop-off: pending order, no attempts, > 24h old, no case yet.
    day_ago = now - timedelta(hours=24)
    for inv in (await db.execute(select(Invoice).where(Invoice.status == "pending",
                                                      Invoice.razorpay_order_id.is_not(None),
                                                      Invoice.created_at <= day_ago))).scalars():
        existing = (await db.execute(select(RecoveryCase).where(RecoveryCase.invoice_id == inv.id))).scalar_one_or_none()
        if existing:
            continue
        cust = await db.get(Customer, inv.customer_id)
        if cust is None or cust.opted_out:
            continue
        case = await open_case(db, cust, inv, "checkout_abandoned", "dropoff_at_otp", actor="agent")
        res = await advance_case(db, case, base_url, actor="agent")
        out["dropoff_detected"] += 1
        out["details"][f"dropoff_{case.seq}"] = res.get("status", "")

    # 0b) AUTO-DETECT B2B overdue invoices (receivables chaser): past due date, no case yet.
    for inv in (await db.execute(select(Invoice).where(Invoice.status.in_(("pending", "failed")),
                                                      Invoice.due_date <= now))).scalars():
        existing = (await db.execute(select(RecoveryCase).where(RecoveryCase.invoice_id == inv.id))).scalar_one_or_none()
        if existing:
            continue
        cust = await db.get(Customer, inv.customer_id)
        if cust is None or cust.opted_out:
            continue
        day_margin = (now - (aware(inv.due_date) or now)).total_seconds() >= 24 * 3600
        if not day_margin:
            continue
        case = await open_case(db, cust, inv, "invoice_overdue", "net15_unpaid", actor="agent")
        res = await advance_case(db, case, base_url, actor="agent")
        out["overdue_detected"] += 1
        out["details"][f"overdue_{case.seq}"] = res.get("status", "")

    # 0c) MANDATE RETRY SEQUENCER: mandate/subscription failures get a fresh charge attempt
    #     on a 24h backoff (configurable), max 2 retries, while the case is open.
    backoff_hours = 24
    try:
        from app.core.config import get_settings as _gs

        backoff_hours = int(getattr(_gs(), "mandate_retry_backoff_hours", 24))
    except Exception:
        pass
    for case in (await db.execute(select(RecoveryCase).where(RecoveryCase.status == "open",
                                                            RecoveryCase.type.in_(("mandate_failed", "subscription_failed"))))).scalars():
        retries = (await db.execute(select(AuditLog).where(AuditLog.case_id == case.id,
                                                          AuditLog.action == "retry_payment"))).scalars().all()
        if len(retries) >= 2:
            continue
        last = max((aware(r.created_at) or now) for r in retries) if retries else (aware(case.created_at) or now)
        if (now - last).total_seconds() < backoff_hours * 3600:
            continue
        cust = await db.get(Customer, case.customer_id)
        res = await act.tool_retry_payment(db, case, cust, base_url)
        if res.get("ok"):
            out["mandate_retries"] += 1
            out["details"][f"retry_{case.seq}"] = f"attempt_{res['attempt']}"
    await db.commit()
    now = datetime.now(timezone.utc)
    # 1) lapsed promises → broken, ladder resumes
    for p in (await db.execute(select(PromiseToPay).where(PromiseToPay.status == "pending"))).scalars():
        if (aware(p.promised_date) or now) > now:
            continue  # still within the hold window
        case = await db.get(RecoveryCase, p.case_id)
        if case and case.status == "open":
            p.status = "broken"
            case.current_stage = "email_sent" if case.current_stage == "promise_wait" else case.current_stage
            await append_audit(db, case_id=case.id, actor="system", action="promise_broken",
                               reason_code="promised_date_passed_unpaid", simulated=False, commit=False)
            out["promises_broken"] += 1
    await db.commit()

    # 2) open cases not waiting on a promise: advance when their last outbound is ≥48h old
    for case in (await db.execute(select(RecoveryCase).where(RecoveryCase.status == "open"))).scalars():
        pending = (await db.execute(select(PromiseToPay).where(PromiseToPay.case_id == case.id, PromiseToPay.status == "pending"))).scalar_one_or_none()
        if pending and (aware(pending.promised_date) or now) > now:
            continue
        last = (await db.execute(select(AuditLog).where(AuditLog.case_id == case.id, AuditLog.channel.in_(("email", "sms", "whatsapp")))
                                 .order_by(AuditLog.id.desc()).limit(1))).scalar_one_or_none()
        if last and (now - (aware(last.created_at) or now)).total_seconds() < 48 * 3600:
            continue
        res = await advance_case(db, case, base_url)
        out["details"][f"case_{case.seq}"] = res["status"]
        if res["status"] == "escalated":
            out["escalated"] += 1
        elif res["status"] not in ("paused_promise_hold",):
            out["advanced"] += 1
    return out


def new_promise_date(days: int) -> datetime:
    return at_9am_ist(datetime.now(timezone.utc) + timedelta(days=days))
