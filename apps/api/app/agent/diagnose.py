"""Root-cause diagnosis. LLM (structured JSON) when configured, deterministic taxonomy otherwise."""
from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.integrations.llm_client import llm_json

log = get_logger("agent.diagnose")

TAXONOMY = ["soft_decline", "hard_decline", "gateway_technical", "voluntary_dropoff", "mandate_failure", "b2b_nonpayment"]

DETERMINISTIC: dict[str, tuple[str, float, str]] = {
    # failure_code → (root_cause, confidence, human note)
    "insufficient_funds": ("soft_decline", 0.92, "Card had insufficient funds — a timed retry or UPI rail usually recovers this."),
    "card_expired": ("hard_decline", 0.95, "Card expired — needs a fresh instrument via payment link."),
    "authentication_failed": ("soft_decline", 0.8, "3DS/OTP step failed — a calmer retry window or UPI works better."),
    "gateway_timeout": ("gateway_technical", 0.9, "Gateway timeout at charge time — idempotent retry is safe."),
    "network_error": ("gateway_technical", 0.85, "Network error between gateway and issuer."),
    "dropoff_at_otp": ("voluntary_dropoff", 0.75, "Customer abandoned at OTP — friction or second thoughts; nudge with 1-tap UPI."),
    "dropoff_at_shipping": ("voluntary_dropoff", 0.7, "Checkout abandoned before payment — price or intent objection."),
    "mandate_auth_expired": ("mandate_failure", 0.9, "e-mandate authorisation lapsed — needs re-authentication."),
    "e_mandate_revoked_by_bank": ("mandate_failure", 0.93, "Bank revoked the mandate (NACH/UPIe) — set up a new mandate."),
    "net15_unpaid": ("b2b_nonpayment", 0.85, "B2B invoice past Net-15 — ap follow-up with a payment link."),
    "net30_unpaid": ("b2b_nonpayment", 0.85, "B2B invoice past Net-30 — ap follow-up with a payment link."),
    "subscription_charge_failed": ("soft_decline", 0.7, "Recurring charge failed — retry on a different rail."),
}

TYPE_DEFAULT = {
    "payment_failed": "soft_decline",
    "checkout_abandoned": "voluntary_dropoff",
    "subscription_failed": "mandate_failure",
    "mandate_failed": "mandate_failure",
    "invoice_overdue": "b2b_nonpayment",
}


async def diagnose(case_type: str, failure_code: str | None, amount_paise: int,
                   customer_name: str | None = None, gemini_key: str | None = None,
                   use_llm: bool = True) -> dict[str, Any]:
    """Returns root_cause, confidence, notes. Structured output only — never free text."""
    # Known provider failure codes are authoritative evidence. The model is never
    # allowed to override a known mapping — this prevents confident hallucinations
    # such as calling "insufficient_funds" a gateway outage.
    known = DETERMINISTIC.get(failure_code or "")
    if known:
        cause, conf, notes = known
        return {"root_cause": cause, "confidence": conf, "notes": notes, "engine": "rules",
                "evidence": f"provider failure code: {failure_code}"}

    if use_llm and (gemini_key or get_settings().openai_api_key or get_settings().anthropic_api_key):
        prompt = (
            f"Classify the root cause of a failed payment for recovery. Case type: {case_type}. "
            f"Failure code: {failure_code}. Amount: ₹{amount_paise // 100:.0f}. Customer: {customer_name or 'unknown'}. "
            f"Choose root_cause strictly from {TAXONOMY}. If evidence is insufficient, choose the case-type default. "
            'Reply JSON only: {"root_cause": "...", "confidence": 0.0-1.0, "notes": "one sentence, max 20 words"}'
        )
        j = await llm_json(prompt, gemini_key=gemini_key)
        if j and j.get("root_cause") in TAXONOMY:
            try:
                conf = float(j.get("confidence", 0.8))
            except (TypeError, ValueError):
                conf = 0.8
            # For unknown codes the model may classify, but confidence is bounded.
            return {"root_cause": j["root_cause"], "confidence": round(min(0.9, max(0.5, conf)), 2),
                    "notes": str(j.get("notes", ""))[:160], "engine": "llm",
                    "evidence": "unmapped provider signal; model classification"}

    cause, conf, notes = DETERMINISTIC.get(failure_code or "", (TYPE_DEFAULT.get(case_type, "soft_decline"), 0.7, "Signal-pattern match from the deterministic taxonomy."))
    return {"root_cause": cause, "confidence": conf, "notes": notes, "engine": "rules",
            "evidence": f"case type default: {case_type}"}
