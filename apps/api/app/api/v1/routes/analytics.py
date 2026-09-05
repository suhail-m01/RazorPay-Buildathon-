"""Analytics: KPI header, baseline-vs-agent, by root cause / channel / product.

Honesty rule: headline KPIs count REAL activity only. Rows from the labeled demo
cohort (@example.test) and evaluation batches are excluded from the headline and
reported separately in `demo` / batch pages.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.decide import aware
from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.base import Customer, Invoice, MerchantUser
from app.models.recovery import AuditLog, PromiseToPay, RecoveryCase

router = APIRouter(prefix="/analytics", tags=["analytics"])

NAIVE_RETRY_BASELINE = 0.38  # documented assumption: naive single-channel retry recovers ~38%
CHANNEL_COST_PAISE = {"email": 5, "sms": 350, "whatsapp": 400, "voice": 2500}
DEMO_DOMAIN = "@example.test"


@router.get("")
async def analytics(db: AsyncSession = Depends(get_db), user: MerchantUser = Depends(get_current_user)) -> dict[str, Any]:
    rows = (await db.execute(select(RecoveryCase, Customer.email)
                             .join(Customer, RecoveryCase.customer_id == Customer.id)
                             .where(RecoveryCase.batch_tag.is_(None)))).all()
    email_of = {r[0].id: r[1] for r in rows}
    is_demo = lambda c: email_of.get(c.id, "").endswith(DEMO_DOMAIN)  # noqa: E731

    real = [r[0] for r in rows if not is_demo(r[0])]
    demo = [r[0] for r in rows if is_demo(r[0])]
    now = datetime.now(timezone.utc)

    open_ = [c for c in real if c.status == "open"]
    recovered = [c for c in real if c.status == "recovered"]
    at_risk = sum(c.amount_paise for c in open_)
    recovered_paise = sum(c.amount_paise for c in recovered)
    rate = len(recovered) / len(real) if real else 0.0

    # time-to-recovery distribution (hours)
    hours = sorted(int(((aware(c.recovered_at) or now) - (aware(c.created_at) or now)).total_seconds() / 3600) for c in recovered if c.recovered_at)

    # cost model: successful channel per recovered case (real only)
    cost_paise = sum(CHANNEL_COST_PAISE.get(c.recovery_channel or "email", 5) for c in recovered)

    by_cause: dict[str, dict[str, int]] = {}
    for c in real:
        e = by_cause.setdefault(c.root_cause or "undetermined", {"cases": 0, "recovered": 0, "amount_paise": 0})
        e["cases"] += 1
        e["amount_paise"] += c.amount_paise
        if c.status == "recovered":
            e["recovered"] += 1

    by_channel: dict[str, dict[str, int]] = {}
    for c in real:
        e = by_channel.setdefault(c.recovery_channel or "none", {"cases": 0, "recovered": 0})
        e["cases"] += 1
        if c.status == "recovered":
            e["recovered"] += 1

    promises = (await db.execute(select(PromiseToPay).join(RecoveryCase, PromiseToPay.case_id == RecoveryCase.id)
                                 .where(RecoveryCase.batch_tag.is_(None)))).scalars().all()
    kept = [p for p in promises if p.status == "kept"]
    broken = [p for p in promises if p.status == "broken"]
    rejected = [p for p in promises if p.status == "rejected"]

    # Direct payment-request money (real, non-demo) — recovered/at-risk outside cases.
    all_invoices = (await db.execute(select(Invoice, Customer.email)
                                     .join(Customer, Invoice.customer_id == Customer.id))).all()
    real_invs = [r[0] for r in all_invoices if not r[1].endswith(DEMO_DOMAIN)]
    case_recovered_invoice_ids = {c.invoice_id for c in recovered}
    direct_paid = [i for i in real_invs if i.status == "paid" and i.id not in case_recovered_invoice_ids]
    pending_requests = [i for i in real_invs if i.status in ("pending", "failed")]
    direct_paid_paise = sum(i.amount_paise for i in direct_paid)
    pending_paise = sum(i.amount_paise for i in pending_requests)

    weekly: list[dict[str, Any]] = []
    for i in range(5, -1, -1):
        start = now - timedelta(weeks=i + 1)
        end = now - timedelta(weeks=i)
        wk = [c for c in recovered if start < (aware(c.recovered_at) or end) <= end]
        baseline = int(sum(c.amount_paise for c in real if start < (aware(c.created_at) or end) <= end) * NAIVE_RETRY_BASELINE)
        weekly.append({"label": f"W-{i}", "agent_paise": sum(c.amount_paise for c in wk), "baseline_paise": baseline})

    # Product-level view (real + demo, each row flagged so the UI can label it).
    inv_by_id = {inv.id: inv for inv in (await db.execute(select(Invoice))).scalars()}
    by_product: dict[str, dict[str, Any]] = {}
    for c in real + demo:
        inv = inv_by_id.get(c.invoice_id)
        name = (inv.title if inv else None) or "Payment request"
        e = by_product.setdefault(name, {"cases": 0, "at_risk_paise": 0, "recovered_paise": 0, "demo": is_demo(c)})
        e["cases"] += 1
        if c.status == "recovered":
            e["recovered_paise"] += c.amount_paise
        elif c.status in ("open", "escalated"):
            e["at_risk_paise"] += c.amount_paise

    # Operational funnel and outcome metrics — derived only from real, non-batch cases.
    stage_counts: dict[str, int] = {}
    stage_value: dict[str, int] = {}
    by_type: dict[str, dict[str, int]] = {}
    for c in real:
        stage_counts[c.current_stage] = stage_counts.get(c.current_stage, 0) + 1
        stage_value[c.current_stage] = stage_value.get(c.current_stage, 0) + c.amount_paise
        typ = by_type.setdefault(c.type, {"cases": 0, "at_risk_paise": 0, "recovered_paise": 0, "recovered": 0})
        typ["cases"] += 1
        if c.status == "recovered":
            typ["recovered"] += 1
            typ["recovered_paise"] += c.amount_paise
        elif c.status in ("open", "escalated"):
            typ["at_risk_paise"] += c.amount_paise

    contacted_case_ids = set((await db.execute(
        select(AuditLog.case_id).where(
            AuditLog.case_id.is_not(None),
            AuditLog.action.in_(("send_email", "send_sms", "send_whatsapp", "place_voice_call"))
        )
    )).scalars().all())
    stopped = [c for c in real if c.status == "stopped"]
    escalated = [c for c in real if c.status == "escalated"]
    avg_hours = round(sum(hours) / len(hours), 1) if hours else 0.0

    return {
        "ok": True,
        "kpis": {
            "at_risk_paise": at_risk + pending_paise, "open_cases": len(open_),
            "recovered_cases": len(recovered), "recovered_paise": recovered_paise + direct_paid_paise,
            "recovery_rate": round(rate, 3),
            "request_payments": len(direct_paid), "direct_paid_paise": direct_paid_paise,
            "pending_requests": len(pending_requests),
            "customers_contacted": len(contacted_case_ids.intersection({c.id for c in real})),
            "stopped_cases": len(stopped), "escalated_cases": len(escalated),
            "avg_recovery_hours": avg_hours,
            "uplift_vs_naive_pct_points": round(max(0.0, rate - NAIVE_RETRY_BASELINE) * 100, 1),
            "cost_to_recover_paise": cost_paise,
            "cost_per_rupee_recovered": round(cost_paise / max(1, recovered_paise + direct_paid_paise), 4),
        },
        "demo": {
            "cases": len(demo),
            "recovered_cases": len([c for c in demo if c.status == "recovered"]),
            "recovered_paise": sum(c.amount_paise for c in demo if c.status == "recovered"),
            "at_risk_paise": sum(c.amount_paise for c in demo if c.status in ("open", "escalated")),
        },
        "by_product": sorted(({"product": k, **v} for k, v in by_product.items()),
                             key=lambda x: -(x["at_risk_paise"] + x["recovered_paise"]))[:8],
        "by_root_cause": by_cause,
        "by_channel": by_channel,
        "by_type": by_type,
        "stage_counts": stage_counts,
        "stage_value": stage_value,
        "time_to_recovery_hours": hours,
        "promises": {"kept": len(kept), "broken": len(broken), "rejected_over_cap": len(rejected), "pending": len([p for p in promises if p.status == "pending"])},
        "weekly": weekly,
    }
