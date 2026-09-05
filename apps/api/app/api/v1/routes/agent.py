"""Grounded merchant command center.

This endpoint intentionally does not let an LLM invent facts or execute arbitrary tools.
It answers a small, auditable command vocabulary from the same analytics/case data the UI uses.
"""
from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.base import Customer, MerchantUser
from app.models.recovery import RecoveryCase

router = APIRouter(prefix="/agent", tags=["agent"])


def money(paise: int) -> str:
    return f"₹{paise / 100:,.0f}"


@router.post("/command")
async def command(body: dict[str, Any], db: AsyncSession = Depends(get_db),
                  user: MerchantUser = Depends(get_current_user)):
    text = str((body or {}).get("text", "")).strip()
    q = re.sub(r"\s+", " ", text.lower())
    if not q:
        return {"ok": False, "supported": True, "message": "Ask about recovered revenue, revenue at risk, recovery rate, top causes, or active cases."}

    # Read from the same source of truth as /analytics, not from model memory.
    rows = (await db.execute(select(RecoveryCase, Customer.email).join(
        Customer, RecoveryCase.customer_id == Customer.id
    ).where(RecoveryCase.batch_tag.is_(None)))).all()
    real = [r[0] for r in rows if not r[1].endswith("@example.test")]
    recovered = [c for c in real if c.status == "recovered"]
    active = [c for c in real if c.status == "open"]
    at_risk = sum(c.amount_paise for c in active)
    recovered_value = sum(c.amount_paise for c in recovered)
    rate = len(recovered) / len(real) if real else 0.0

    if any(k in q for k in ("how much did we recover", "recovered revenue", "money recovered", "revenue recovered")):
        return {"ok": True, "intent": "recovered_revenue", "message": f"{money(recovered_value)} recovered across {len(recovered)} cases.", "source": "live analytics"}
    if any(k in q for k in ("at risk", "revenue risk", "risk")):
        return {"ok": True, "intent": "revenue_at_risk", "message": f"{money(at_risk)} is currently at risk across {len(active)} open cases.", "source": "live analytics"}
    if "recovery rate" in q or "recovered %" in q:
        return {"ok": True, "intent": "recovery_rate", "message": f"{rate * 100:.1f}% recovery rate ({len(recovered)}/{len(real)} cases).", "source": "live analytics"}
    if any(k in q for k in ("active cases", "open cases", "how many cases")):
        return {"ok": True, "intent": "active_cases", "message": f"{len(active)} active recovery cases.", "source": "live analytics"}
    if any(k in q for k in ("top cause", "root cause", "why are payments failing")):
        counts: dict[str, int] = {}
        for c in real:
            cause = c.root_cause or "undetermined"
            counts[cause] = counts.get(cause, 0) + c.amount_paise
        top = sorted(counts.items(), key=lambda x: -x[1])[:3]
        return {"ok": True, "intent": "top_causes",
                "message": "Top revenue-at-risk causes: " + ", ".join(f"{k.replace('_',' ')} ({money(v)})" for k, v in top),
                "source": "live case data"}
    if "high value" in q or "above ₹5000" in q or "above 5000" in q:
        cases = [c for c in active if c.amount_paise >= 500000]
        return {"ok": True, "intent": "high_value", "message": f"{len(cases)} open cases are at or above ₹5,000.", "source": "live case data"}

    return {
        "ok": True, "intent": "unsupported",
        "message": "I won't guess or execute an unsupported command. Try: “How much did we recover?”, “What is revenue at risk?”, “Show recovery rate”, or “Top causes”.",
        "source": "grounded command router",
        "suggested_actions": ["Open Recovery Cases", "Open Analytics", "Run a measured batch"],
    }
