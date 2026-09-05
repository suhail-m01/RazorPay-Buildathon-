"""IST schedule helpers + deterministic policy engine (LLM proposes, rules dispose)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.models.base import Customer
from app.models.recovery import PromiseToPay, RecoveryCase

IST = ZoneInfo("Asia/Kolkata")
MAX_OUTBOUND_AFTER_FIRST_EMAIL = 3
PROMISE_CAP_DAYS = 7
CHANNEL_COST_PAISE = {"email": 5, "sms": 350, "whatsapp": 400, "voice": 2500}

QUIET_START, QUIET_END = 21, 9


def aware(dt: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes — normalise to UTC-aware before comparing."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def ist_now() -> datetime:
    return datetime.now(IST)


def is_quiet_hours(dt: datetime | None = None) -> bool:
    dt = dt or ist_now()
    hour = dt.hour
    return hour >= QUIET_START or hour < QUIET_END


def at_9am_ist(day: datetime) -> datetime:
    d = day.astimezone(IST)
    return datetime(d.year, d.month, d.day, 9, 0, tzinfo=IST).astimezone(timezone.utc)


def days_between(a: datetime, b: datetime) -> int:
    a = a.astimezone(IST); b = b.astimezone(IST)
    return (datetime(b.year, b.month, b.day) - datetime(a.year, a.month, a.day)).days


@dataclass
class Decision:
    allowed: bool
    action: str
    channel: str | None = None
    reason_code: str | None = None
    checks: dict | None = None


def _checks(**kw) -> dict:
    return kw


def evaluate_policy(case: RecoveryCase, customer: Customer, pending_promise: PromiseToPay | None,
                    proposed: str, now: datetime | None = None) -> Decision:
    """The ONLY place outbound is authorised. Every rule is code — no LLM override."""
    now = now or ist_now()
    checks: dict = {"proposed": proposed, "opted_out": customer.opted_out, "quiet_hours_ist": is_quiet_hours(now),
                    "attempts": case.attempts_count, "cap": MAX_OUTBOUND_AFTER_FIRST_EMAIL}

    def block(reason: str) -> Decision:
        return Decision(False, proposed, None, reason, checks)

    if case.status == "recovered":
        return block("already_recovered")
    if customer.opted_out:
        return block("customer_opted_out")  # blocking, always
    if pending_promise is not None and aware(pending_promise.promised_date) > now:
        checks["promise_until"] = pending_promise.promised_date.isoformat()
        return block("active_promise_hold")
    if proposed in ("send_sms", "send_whatsapp", "place_voice_call", "retry_payment") and case.attempts_count >= MAX_OUTBOUND_AFTER_FIRST_EMAIL:
        return block("attempt_cap_reached")
    if proposed in ("send_sms", "send_whatsapp") and case.type == "checkout_abandoned" and case.attempts_count >= 1:
        return block("attempt_cap_reached")

    consent_map = {"send_email": "consent_email", "send_sms": "consent_sms", "send_whatsapp": "consent_whatsapp",
                   "place_voice_call": "consent_sms"}
    consent_field = consent_map.get(proposed)
    if consent_field and not getattr(customer, consent_field):
        checks["missing_consent"] = consent_field
        return Decision(False, proposed, proposed.replace("send_", ""), f"no_{consent_field}", checks)

    channel_for_action = {
        "send_email": "email",
        "send_sms": "sms",
        "send_whatsapp": "whatsapp",
        "place_voice_call": "voice",
        "retry_payment": "sms",
    }.get(proposed)

    if proposed in ("send_sms", "send_whatsapp", "place_voice_call") and is_quiet_hours(now):
        return Decision(False, proposed, channel_for_action, "quiet_hours_21_09_ist", checks)

    cost = CHANNEL_COST_PAISE.get(channel_for_action or "", 0)
    checks["est_cost_paise"] = cost
    if cost and cost > 0 and case.amount_paise < cost * 10:
        return Decision(False, proposed, None, "cost_exceeds_10pct_of_amount", checks)

    if proposed == "offer_discount" and checks.get("discount_pct", 0) > 5:
        return block("discount_above_5pct_not_allowed")

    return Decision(True, proposed, channel_for_action, "policy_pass", checks)



def choose_primary_channel(case: RecoveryCase, customer: Customer) -> str:
    """Choose exactly one primary recovery channel: email, WhatsApp, or voice.

    Rules are deterministic so the LLM cannot bypass consent or economics:
    high-risk/high-value cases may receive a call, opted-in WhatsApp is preferred
    for medium risk, and email is the safe/default channel.
    """
    preferred = (customer.preferred_channel or "email").lower()

    if (
        case.risk_score >= 72
        and case.amount_paise >= 100_000
        and bool(customer.phone)
        and customer.consent_sms
    ):
        return "voice"

    if customer.consent_whatsapp and bool(customer.phone) and (preferred == "whatsapp" or case.risk_score >= 38):
        return "whatsapp"

    if customer.consent_email and bool(customer.email):
        return "email"

    if customer.consent_whatsapp and bool(customer.phone):
        return "whatsapp"

    if customer.consent_sms and bool(customer.phone):
        return "voice"

    return "email"

def compute_risk(case: RecoveryCase, days_overdue: int, broken_promises: int) -> int:
    exposure = min(40, case.amount_paise // 250_000)          # ₹2,500 per point, capped
    ageing = min(30, days_overdue * 2)
    attempts = min(15, case.attempts_count * 5)
    history = min(15, broken_promises * 10)
    return max(0, min(100, exposure + ageing + attempts + history))


def risk_tone(score: int) -> str:
    return "sla" if score >= 70 else "warn" if score >= 40 else "brand"
