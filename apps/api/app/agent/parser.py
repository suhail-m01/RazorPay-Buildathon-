"""Promise-to-pay reply parser — deterministic bilingual rules first, LLM refines when
available. The ≤7-day ruling is ALWAYS applied in code after parsing (rules dispose)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
Intent = Literal["promise", "paid", "stop", "dispute", "unknown"]

STOP_RE = re.compile(r"\b(stop|unsubscribe|do not contact|don'?t contact|dont contact|remove me|quit|opt out|no more|block)\b|band kar|mat bhejo|nahi chahiye|na chahiye|dnd", re.I)
DISPUTE_RE = re.compile(r"\b(dispute|wrong|incorrect|fraud|not mine|refund|charged twice|double charge|extra charge|already cancel)\b|galat|mera nah", re.I)
PAID_RE = re.compile(r"\b(paid|payment done|already paid|debited|deducted|money sent|transferred|cleared|ho gaya|ho gya|hogaya|bhej diya|chal gaya)\b", re.I)
PROMISE_HINT_RE = re.compile(r"\b(promise|will pay|i can pay|pay (on|by|in|after)|salary|kal|tomorrow|parso|next (week|month)|agle|agla|after \d|din|days?|tarikh|date)\b|\b\d{1,2}\s*(th|st|nd|rd)\b|\d{4}-\d{2}-\d{2}", re.I)

NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "ek": 1, "do": 2, "teen": 3, "chaar": 4, "char": 4, "paanch": 5, "panch": 5, "chhe": 6, "che": 6, "saat": 7, "aath": 8, "nau": 9, "das": 10}
WEEKDAYS = {"sunday": 6, "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5}  # ISO weekday (Mon=1..Sun=7)
MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}


@dataclass
class ParsedReply:
    intent: Intent
    days: int | None = None
    date_iso: str | None = None
    amount_paise: int | None = None
    reason: str | None = None
    engine: str = "rules"


def _extract_days(text: str) -> int | None:
    """Returns day-count, or 99 as an explicit 'far beyond cap' marker."""
    low = text.lower()
    iso = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", low)
    if iso:
        d = date.fromisoformat(iso.group(1))
        today = datetime.now(IST).date()
        return (d - today).days

    m = re.search(r"(\d{1,3})\s*(?:-?\s*)?(?:days?|din|dino|dinon|day)\b", low) or re.search(r"\b(?:after|in|andar)\s+(\d{1,3})\b", low)
    if m:
        return int(m.group(1))
    for w, n in NUM_WORDS.items():
        if re.search(rf"\b{w}\s*(?:days?|din|dino|dinon)\b", low) or (n <= 7 and re.search(rf"\b(?:in|after)\s+{w}\b", low)):
            return n
    if re.search(r"\b(tomorrow|kal)\b", low):
        return 1
    if re.search(r"\b(day after tomorrow|parso|perso)\b", low):
        return 2
    if re.search(r"\b(next week|agle hafte|agla hafta)\b", low):
        return 7
    for wd, iso_num in WEEKDAYS.items():
        if re.search(rf"\b{wd}\b", low):
            today = datetime.now(IST).date()
            delta = (iso_num - today.isoweekday()) % 7 or 7
            return delta
    dm = re.search(r"\b(\d{1,2})(?:th|st|nd|rd)?\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)", low)
    if dm:
        today = datetime.now(IST).date()
        try:
            target = date(today.year, MONTHS[dm.group(2)], int(dm.group(1)))
            if target < today:
                target = date(today.year + 1, MONTHS[dm.group(2)], int(dm.group(1)))
            return (target - today).days
        except ValueError:
            pass
    if re.search(r"\b(next month|next mahine|agle mahine|agla mahina|15 days|twenty days|\d{2,}\s*(?:days?|din)|two weeks|fortnight|after salary|salary aa|paise aane)\b", low):
        return 99
    return None


def _extract_amount(text: str) -> int | None:
    m = re.search(r"(?:₹|rs\.?|rupees?)\s*([\d,]+(?:\.\d{1,2})?)|([\d,]+(?:\.\d{1,2})?)\s*(?:₹|rupees|rs\.?)", text, re.I)
    raw = (m.group(1) or m.group(2)) if m else None
    if not raw:
        return None
    try:
        n = float(raw.replace(",", ""))
        return int(n * 100) if n >= 1 else None
    except ValueError:
        return None


def rule_parse(text: str) -> ParsedReply:
    t = text.strip()
    if not t:
        return ParsedReply("unknown")
    looks_like_promise = bool(PROMISE_HINT_RE.search(t))
    if STOP_RE.search(t):
        return ParsedReply("stop", reason=t[:160])
    if DISPUTE_RE.search(t) and not looks_like_promise:
        return ParsedReply("dispute", reason=t[:160])
    if looks_like_promise:
        return ParsedReply("promise", days=_extract_days(t), amount_paise=_extract_amount(t), reason=t[:160])
    if PAID_RE.search(t):
        return ParsedReply("paid")
    return ParsedReply("unknown", reason=t[:160])


async def parse_reply(text: str, gemini_key: str | None = None) -> ParsedReply:
    """LLM first (strict JSON), deterministic rules as arbiter + fallback."""
    from app.integrations.llm_client import llm_json

    parsed = rule_parse(text)
    j = await llm_json(gemini_key=gemini_key, prompt="Classify this borrower reply. JSON only: {\"intent\":\"promise|paid|stop|dispute|unknown\","
        "\"days\":integer 1-7 or null,\"amount_paise\":integer or null,\"reason\":\"short quote\"}. "
        f"More than 7 days or vague timing → days null. Text: \"\"\"{text[:400]}\"\"\""
    )
    if j and j.get("intent") in ("promise", "paid", "stop", "dispute", "unknown"):
        llm_intent = j["intent"]
        if llm_intent == "promise" and parsed.intent != "promise":
            llm_intent = parsed.intent  # deterministic regex saw no promise wording — rules dispose
        days = j.get("days") if isinstance(j.get("days"), int) else None
        return ParsedReply(llm_intent, days=days if llm_intent != "promise" else (days if parsed.days is None else parsed.days),
                           amount_paise=j.get("amount_paise") if isinstance(j.get("amount_paise"), int) else parsed.amount_paise,
                           reason=str(j.get("reason", ""))[:160] or parsed.reason, engine="llm")
    return parsed


def apply_promise_rules(parsed: ParsedReply) -> tuple[bool, int | None, str]:
    """CODE-enforced: promise accepted only for 1–7 days ahead. Returns (ok, days, reject_reason)."""
    if parsed.intent != "promise":
        return False, None, "not_promise"
    if parsed.days is None:
        return False, None, "vague_no_date"
    if parsed.days == 99:
        return False, None, "too_far_beyond_7d_cap"
    if parsed.days < 0:
        return False, None, "date_in_past"
    if parsed.days == 0:
        return True, 1, ""  # "today" → resume tomorrow 09:00 IST
    if parsed.days > 7:
        return False, None, f"too_far_{parsed.days}d_over_cap"
    return True, parsed.days, ""
