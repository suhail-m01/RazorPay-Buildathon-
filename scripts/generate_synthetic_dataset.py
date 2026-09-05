"""Synthetic dataset generator — Faker (en_IN), ~92 rows.
Emails use the IANA-reserved non-routable @example.test domain; phones use +91 99999xxxxx.
is_demo_contact stays False → the Act-layer gate guarantees zero real dispatch."""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from faker import Faker

fake = Faker("en_IN")
Faker.seed(20260902)
random.seed(20260902)

CASE_TYPES = ["payment_failed", "checkout_abandoned", "subscription_failed", "mandate_failed", "invoice_overdue"]
FAILURES = {
    "payment_failed": ["insufficient_funds", "card_expired", "authentication_failed"],
    "checkout_abandoned": ["dropoff_at_otp", "dropoff_at_shipping"],
    "subscription_failed": ["subscription_charge_failed", "mandate_auth_expired"],
    "mandate_failed": ["e_mandate_revoked_by_bank", "mandate_auth_expired"],
    "invoice_overdue": ["net15_unpaid", "net30_unpaid"],
}
LANGS = ["en-IN", "hi-IN", "ta-IN", "te-IN", "mr-IN"]
PRODUCTS = [("RecoverPay POS Pro", 249900, "monthly"), ("RecoverPay Analytics", 499900, "monthly"),
            ("RecoverPay Inventory Sync", 129900, "monthly"), ("Storefront Builder Pack", 850000, "installment"),
            ("Onboarding & Migration Pack", 1250000, "installment")]


def generate(count: int = 92) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    while len(rows) < count:
        name = fake.name()
        email = f"{name.lower().replace(' ', '.').replace('.', '')}{len(rows)}@example.test"
        if email in seen:
            continue
        seen.add(email)
        case_type = CASE_TYPES[len(rows) % len(CASE_TYPES)]
        product, price, cycle = PRODUCTS[len(rows) % len(PRODUCTS)]
        stage_roll = random.random()
        # realistic pipeline distribution
        if stage_roll < 0.08:
            stage, status = "detected", "open"
        elif stage_roll < 0.30:
            stage, status = "email_sent", "open"
        elif stage_roll < 0.40:
            stage, status = "whatsapp_sent", "open"
        elif stage_roll < 0.48:
            stage, status = "promise_wait", "open"
        elif stage_roll < 0.93:
            stage, status = "recovered", "recovered"
        else:
            stage, status = "escalated", "escalated"
        created_days_ago = random.randint(2, 85)
        recovered_days_ago = created_days_ago - random.randint(1, max(1, created_days_ago - 1)) if status == "recovered" else None
        rows.append({
            "name": name,
            "email": email,
            "phone": f"+9199999{random.randint(10000, 99999):05d}"[:3 + 9],  # +91 99999xxxxx
            "language": random.choice(LANGS),
            "consents": {"email": True, "sms": random.random() > 0.25, "whatsapp": random.random() > 0.3},
            "preferred_channel": random.choice(["email", "sms", "whatsapp"]),
            "product": product, "amount_paise": price, "billing_cycle": cycle,
            "case_type": case_type, "failure_code": random.choice(FAILURES[case_type]),
            "stage": stage, "status": status, "attempts": {"email_sent": 0, "whatsapp_sent": 1, "promise_wait": 1,
                                                            "recovered": random.randint(0, 2), "escalated": 3, "detected": 0}[stage],
            "risk_score": random.randint(10, 95),
            "created_days_ago": created_days_ago,
            "recovered_days_ago": recovered_days_ago,
        })
    return rows


if __name__ == "__main__":
    out = Path(__file__).parent / "synthetic_dataset.json"
    data = generate()
    out.write_text(json.dumps(data, indent=1))
    print(f"wrote {len(data)} synthetic cases → {out}")
