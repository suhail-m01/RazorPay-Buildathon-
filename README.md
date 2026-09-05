# RecoverPay AI

An AI-powered revenue-recovery platform for Razorpay merchants. A bounded agent runs the loop
**Detect → Diagnose → Decide → Act → Track → Escalate/Stop** over real Razorpay webhooks, with every
decision gated by a deterministic compliance layer and recorded to a tamper-evident, hash-chained audit log.

Two portals, both with login pages:

- **Merchant console** (`/login`) — revenue-at-risk KPIs, live case queue (LIVE badges on real contacts), case files with the full action timeline and compliance checks, human-in-the-loop approvals, audit viewer with chain verification + CSV export, playbooks, agent-vs-naive-retry analytics.
- **Customer portal** (`/portal/login`) — what you owe and why it failed, Razorpay Checkout (or the in-app test-mode checkout on the same capture path), promise-to-pay (≤ 7 days, enforced in code), history, one-tap opt-out. Magic links (`/p/<token>`) also work without a password.

```
apps/
  api/       FastAPI (async, Pydantic v2, SQLAlchemy 2.0, structlog, APScheduler)
  web/       Next.js 14 (App Router, TS strict, Tailwind, TanStack Query, Zustand,
             Recharts, Framer Motion) — both portals as route groups
scripts/     generate_synthetic_dataset.py · demo_contacts.example.py · seed_all.py
docker-compose.yml   web + api + worker + postgres + redis
.github/     CI: pytest · tsc · builds · dependency audit
```

## Quick start (local, SQLite — zero external services)

```bash
cd apps/api && pip install -r requirements.txt && cp ../../.env.example .env
python ../../scripts/seed_all.py          # merchant users + 1 live contact + 92 synthetic cases
uvicorn app.main:app --port 8000          # API + scheduler (AUTO_TICK)

cd ../web && npm i
npm run dev                                # http://localhost:3000  (proxies /api/v1 → :8000)
```

**Logins** — Merchant: `anjali@kirana.cloud` / `Punah@123` (or register your own company).
Customer: register with the seeded live-contact email, or any email (new accounts link to matching dues automatically).

**Full stack (Postgres + Redis + worker):** `docker compose up --build` with `SEED_ON_BOOT=true` on first boot.
Set `DATABASE_URL=postgresql+asyncpg://recoverpay:recoverpay@postgres:5432/recoverpay`.

**Migrations:** dev uses `create_all` on startup; for managed schemas run
`alembic revision --autogenerate -m "init" && alembic upgrade head` (alembic.ini at repo root).

## Why this design (the two decisions judges will ask about)

1. **Bounded agent, not an autonomous loop.** The LLM only classifies root cause (strict JSON into a fixed
   taxonomy) and drafts copy. Every state transition goes through `agent/decide.py` — a pure-function policy
   engine (consent, opt-out, quiet hours 21:00–09:00 IST, attempt caps, cost-vs-amount, promise cap).
   *LLM proposes, rules dispose.* A hallucination cannot spend money or break compliance.
2. **`is_demo_contact` as an architectural gate.** 92 synthetic cases (`@example.test` emails, `+91 99999xxxxx`
   phones) power realistic analytics, but the gate lives **inside** the lowest-level send functions
   (`agent/act.py`) — synthetic contacts are physically incapable of triggering a real Twilio/Resend dispatch,
   no matter which code path asks. Simulated sends still write full audit rows flagged `simulated: true`.
3. **Honest audit.** The `AuditLog` is append-only with a SHA-256 hash chain; `/api/v1/cases/audit/verify`
   walks it and any edit/delete breaks verification. Exports are PII-masked (`r***@domain`, `+91*****210`).

## The 7-day promise rule (try it live)

Open any case → **Simulate a customer reply**:
- `3 din baad payment kar dunga` → accepted, hold until the promised date 09:00 IST, all channels paused.
- `next month salary aa jayega` → **rejected in code** (`too_far_beyond_7d_cap`) with a polite auto-reply.
- `stop contacting me` → case `stopped`, opt-out enforced on every future send path.
The same engine (`agent/parser.py` + `track.py`) serves portal replies, date pickers and email hooks.

## Payments

- With `RAZORPAY_KEY_ID/SECRET`: Orders API + hosted Checkout + Payment Links; `payment.captured` /
  `payment.failed` / `subscription.charged.failed` webhooks verified with HMAC-SHA256 (`x-razorpay-signature`),
  401 on mismatch. Card entry stays entirely client-side (out of PCI scope).
- Without keys: the in-app test-mode checkout runs the **same capture service** as the webhook — there is no
  way to "mark paid" that skips the real code path. Test card: `4111 1111 1111 1111`.
- Local webhook testing: `ngrok http 8000` → point Razorpay webhooks at `<tunnel>/api/v1/webhooks/razorpay`.

## Before you demo (channel pre-flight)

1. **Seed live contacts** — copy `scripts/demo_contacts.example.py` → `scripts/demo_contacts.py` (gitignored)
   with your real email/phone, or set `DEMO_CONTACTS_JSON`/`FOUNDER_EMAIL` env, then re-seed. Only
   LIVE-badged rows will ever dispatch for real.
2. **Email (Resend)** — set `RESEND_API_KEY`. Trial sender `onboarding@resend.dev` delivers only to the
   account owner's address; verify a domain for other recipients.
3. **SMS/Voice (Twilio trial)** — every recipient phone must be added under **Verified Caller IDs** first.
4. **WhatsApp (Twilio Sandbox)** — each demo phone must send `join <sandbox-code>` from their own WhatsApp,
   and the join **expires after 72h** — refresh before each demo session.
5. **Razorpay** — test-mode keys + webhook secret; webhook URL from ngrok or your deployed host.
6. **60-second script:** log in → Inject test case (watch Detect→Act in the live feed) → open a case →
   simulate “3 din baad” vs “next month” → Approvals → Audit verify chain → portal login → Pay now →
   receipt + case recovered.

## Tests

`cd apps/api && python -m pytest tests/ -q` — policy guardrails (opt-out, consent, caps, quiet hours),
promise ≤7d rules (incl. Hinglish), webhook signature verification, and the is_demo_contact send-gate
(synthetic contacts never reach channel clients).

## Live-channel checklist (Settings page)

- **AI (Gemini, free tier):** key from https://aistudio.google.com/apikey → Settings → AI card → **Test AI diagnosis** (runs a real classified diagnosis).
- **WhatsApp (Twilio):** trial account → the demo phone must send `join <sandbox-code>` to the sandbox number (**expires every 72h** — refresh before presenting), then Settings → WhatsApp card → **Send test**.
- **Hosted webhooks:** Settings shows the exact URL to register in the Razorpay dashboard (`…/api/v1/webhooks/razorpay`); signature is verified (HMAC-SHA256, 401 on mismatch). Locally: `ngrok http 8000`.
- **Honesty labels:** headline dashboard KPIs count real activity only; demo cohort (@example.test) and evaluation batches are reported separately and labeled.


## Premium agentic upgrade (Track 03)

The latest UI evolves the merchant console into a **Revenue Recovery Control Center** while preserving the existing recovery FSM, payment/webhook path, policy engine, audit chain, integrations and demo safety.

New merchant experiences:
- `/app` — revenue-at-risk command centre with measured recovery, lifecycle pipeline, SSE recovery feed and visible guardrail outcomes.
- `/app/agent` — grounded merchant command console. It answers a deliberately bounded set of questions from live analytics and refuses unsupported requests rather than inventing facts.
- `/app/analytics` — recovery funnel, revenue leakage by cause/type, intervention performance and lifecycle distribution.
- Case detail — recovery journey, AI diagnosis evidence, AI-vs-policy decision trace and premium recovered state.
- Batch — explicit “The Bar” view with batch revenue at risk, measured recovered money, cost/net outcome and funnel counts.

### Anti-hallucination rule

Known provider failure codes are treated as authoritative evidence by the diagnosis engine. Gemini/LLM classification is only used for unmapped signals; it cannot override a deterministic mapping for a known failure code. Diagnosis audit events record the evidence source.

All financial headline metrics continue to exclude `@example.test` synthetic/batch cohorts unless a page explicitly identifies them as demo/evaluation data.

## Twilio + premium UI update

This version adds real Twilio Voice dispatch, WhatsApp trial-template support, Twilio status endpoints, a channel plan on Payment Requests, and a premium animated AI signal system. Public landing-page metrics are abstracted so merchant revenue figures are not exposed; authenticated merchant analytics remain available inside the command center.

See `TWILIO_SETUP.md` for the Twilio trial limitation and webhook configuration. See `RUN_PROJECT_UPDATED.md` for the minimal VS Code run commands.
