# RecoverPay AI — a real app you USE to demonstrate

No seeded demo data. You connect your own accounts, add real customers, and every case in
the system comes from a real payment event. The demo IS you using the product.

## Run it

```bash
# 1. API  (terminal 1)
cd apps/api
pip install -r requirements.txt
cp ../../.env.example .env
python ../../scripts/seed_all.py     # creates just your login + playbooks (no fake data)
python -m uvicorn app.main:app --reload --port 8000

# 2. Web   (terminal 2)
cd apps/web
npm install
npm run dev                          # http://localhost:3000
```

**Merchant login:** `anjali@kirana.cloud` / `Punah@123` (or register your own company at `/register`).
Customer portal: `/portal/register` with any email — dues link up automatically.

## First 5 minutes (the real setup)

1. **Settings** (top nav) → paste YOUR Razorpay **test** keys (`rzp_test_…`) → **Test connection**
   → add email (Resend key, or Gmail: 2-step verification → App Password → SMTP) → **Send test**.
2. **Requests** → *New customer* (use your own email/phone) → create a **payment request** →
   the real Razorpay link is generated and emailed to you.
3. Open the link (or log into the customer portal) → **Pay now** → Razorpay Checkout:
   - `4111 1111 1111 1111` → payment **succeeds** → invoice paid, receipt issued
   - `4000 0000 0000 0002` → payment **declines** (real failure!) → back in the console hit
     **Sync status** → the agent opens a case, diagnoses it, and sends the recovery email
     (check your inbox) → customer pays → **Recovered**.
4. Watch it all land in **Dashboard** (live feed), **Case queue**, and **Audit** (verify the chain).

Every number on screen is real activity by you — nothing is pre-seeded or faked.

## Notes

- Without Razorpay keys the app still runs end-to-end on a built-in test checkout (same capture
  code path) — but real keys make declines/captures genuine Razorpay events.
- For hosted webhooks (`payment.captured` etc.): run `ngrok http 8000`, add the URL
  `https://<tunnel>/api/v1/webhooks/razorpay` in the Razorpay dashboard with your webhook secret
  in Settings. Checkout + Sync already work without webhooks.
- Tests: `cd apps/api && python -m pytest tests/ -q`
