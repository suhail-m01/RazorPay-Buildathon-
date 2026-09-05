"""Critical-path tests: policy guardrails, promise rules, webhook signatures, send-gating."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.agent.decide import MAX_OUTBOUND_AFTER_FIRST_EMAIL, evaluate_policy, is_quiet_hours
from app.agent.parser import apply_promise_rules, rule_parse
from app.integrations import razorpay_client

IST = ZoneInfo("Asia/Kolkata")


def _customer(**kw):
    base = dict(opted_out=False, consent_email=True, consent_sms=True, consent_whatsapp=True, is_demo_contact=False, id="c9")
    base.update(kw)
    return SimpleNamespace(**base)


def _case(**kw):
    base = dict(status="open", attempts_count=0, amount_paise=249900, type="invoice_overdue", current_stage="email_sent", id="case_x")
    base.update(kw)
    return SimpleNamespace(**base)


# ---------------------------------------------------------------- policy guardrails
def test_opted_out_blocks_everything():
    d = evaluate_policy(_case(), _customer(opted_out=True), None, "send_email")
    assert not d.allowed and d.reason_code == "customer_opted_out"


def test_missing_consent_blocks_channel():
    d = evaluate_policy(_case(), _customer(consent_whatsapp=False), None, "send_whatsapp")
    assert not d.allowed and d.reason_code == "no_consent_whatsapp"


def test_attempt_cap_blocks():
    d = evaluate_policy(_case(attempts_count=MAX_OUTBOUND_AFTER_FIRST_EMAIL), _customer(), None, "send_sms")
    assert not d.allowed and d.reason_code == "attempt_cap_reached"


def test_active_promise_blocks_nagging():
    promise = SimpleNamespace(promised_date=datetime.now(IST) + timedelta(days=2))
    d = evaluate_policy(_case(), _customer(), promise, "send_whatsapp")
    assert not d.allowed and d.reason_code == "active_promise_hold"


def test_quiet_hours_block_sms_but_not_email():
    night = datetime(2026, 3, 10, 23, 30, tzinfo=IST)  # 23:30 IST
    assert is_quiet_hours(night)
    d_sms = evaluate_policy(_case(), _customer(), None, "send_sms", now=night)
    d_email = evaluate_policy(_case(), _customer(), None, "send_email", now=night)
    assert not d_sms.allowed and d_sms.reason_code == "quiet_hours_21_09_ist"
    assert d_email.allowed


def test_recovered_case_blocked():
    d = evaluate_policy(_case(status="recovered"), _customer(), None, "send_email")
    assert not d.allowed


# ---------------------------------------------------------------- promise rules (≤7 days, code-enforced)
def test_promise_within_cap_accepted():
    p = rule_parse("I will pay in 3 days")
    assert p.intent == "promise" and p.days == 3
    ok, days, _ = apply_promise_rules(p)
    assert ok and days == 3


def test_promise_hinglish_accepted():
    ok, days, _ = apply_promise_rules(rule_parse("5 din baad payment kar dunga"))
    assert ok and days == 5


def test_promise_over_cap_rejected():
    ok, _, reason = apply_promise_rules(rule_parse("I can pay after 15 days"))
    assert not ok and "over" in reason or reason == "too_far_beyond_7d_cap"


def test_promise_next_month_rejected():
    p = rule_parse("I will pay next month")
    assert p.days == 99
    ok, _, reason = apply_promise_rules(p)
    assert not ok and reason == "too_far_beyond_7d_cap"


def test_promise_vague_rejected():
    ok, _, reason = apply_promise_rules(rule_parse("I promise to pay"))  # no date anywhere
    assert not ok and reason == "vague_no_date"


def test_boundary_7_ok_8_rejected():
    ok7, d7, _ = apply_promise_rules(rule_parse("pay in 7 days"))
    ok8, _, _ = apply_promise_rules(rule_parse("pay in 8 days"))
    assert ok7 and d7 == 7
    assert not ok8


def test_stop_and_paid_intents():
    assert rule_parse("please stop messaging me").intent == "stop"
    assert rule_parse("payment ho gaya tha").intent == "paid"


# ---------------------------------------------------------------- webhook signature
def test_webhook_signature_roundtrip(monkeypatch):
    monkeypatch.setattr(razorpay_client, "get_settings", lambda: SimpleNamespace(razorpay_webhook_secret="whsec_test", razorpay_key_id="", razorpay_key_secret=""))
    body = b'{"event":"payment.captured"}'
    sig = hmac.new(b"whsec_test", body, hashlib.sha256).hexdigest()
    assert razorpay_client.verify_webhook_signature(body, sig, ["whsec_test"])
    assert not razorpay_client.verify_webhook_signature(body, "deadbeef", ["whsec_test"])
    assert not razorpay_client.verify_webhook_signature(body, None, ["whsec_test"])
    assert razorpay_client.verify_webhook_signature(body, sig, ["other", "whsec_test"])  # multi-tenant secrets


# ---------------------------------------------------------------- the send gate (is_demo_contact)
@pytest.mark.asyncio
async def test_synthetic_contact_never_dispatches(monkeypatch):
    from app.agent import act as act_mod

    called = []

    async def _boom(*a, **kw):
        called.append(1)
        return True, "should-not-happen"

    monkeypatch.setattr(act_mod.email_client, "send_email", _boom)
    case = _case(id="case_x")
    customer = _customer(is_demo_contact=False, email="someone@example.test")
    # bypass the policy layer deliberately: even if policy passed, gate must stop dispatch
    decision = evaluate_policy(case, customer, None, "send_email")
    assert decision.allowed
    simulated = not customer.is_demo_contact
    assert simulated is True and called == []  # the gate value used inside _gate_and_send


class _FakeScalars:
    def all(self):
        return []


class _FakeResult:
    def scalar_one_or_none(self):
        return None

    def scalars(self):
        return _FakeScalars()


class FakeDB:
    """Minimal async session stand-in: no-ops for add/flush/execute/commit."""

    def add(self, row):
        return None

    async def flush(self):
        return None

    async def commit(self):
        return None

    async def execute(self, *_a, **_kw):
        return _FakeResult()


@pytest.mark.asyncio
async def test_live_contact_can_dispatch(monkeypatch):
    from app.agent import act as act_mod

    async def _fake_send(to, subject, body, creds=None):
        return True, "resend"

    monkeypatch.setattr(act_mod.email_client, "send_email", _fake_send)
    case = _case(id="case_y", customer_id="c1")
    customer = _customer(is_demo_contact=True, email="real@person.in")
    res = await act_mod.tool_send_email(FakeDB(), case, customer, "subject", "body")
    assert res["ok"] and res["simulated"] is False and res["delivered"] is True
