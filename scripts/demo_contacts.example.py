"""LIVE demo contacts — REAL PII, NEVER COMMITTED WITH REAL DATA.

Copy this file to scripts/demo_contacts.py (gitignored) and fill in your real details.
These rows are seeded with is_demo_contact=True: the ONLY contacts for which the
Act layer will ever dispatch a real email/SMS/WhatsApp.

Each entry should span a different case type so every demo-worthy feature has a
dedicated real contact. At least one should demo the 2-way reply flow.

DEMO_CONTACTS = [
    {"name": "Your Name", "email": "you@gmail.com", "phone": "+9198xxxxxxxx",
     "language": "en-IN", "case_type": "payment_failed", "channel": "email",
     "note": "primary — receives real dunning email; reply to demo the promise parser"},
    ...
]
"""

import os

_raw = os.environ.get("DEMO_CONTACTS_JSON", "[]")
try:
    import json

    DEMO_CONTACTS: list[dict] = json.loads(_raw)
except Exception:
    DEMO_CONTACTS = []
