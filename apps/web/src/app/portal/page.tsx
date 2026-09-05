"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, fmtINR, fmtD, fmtDT, CAUSE_LABEL, clearSessions } from "@/lib/api";
import { Badge, Logo, Skeleton } from "@/components/ui";
import { AnimatePresence, FadeIn, motion } from "@/lib/motion";
import { useUI } from "@/lib/store";

type Me = {
  customer: { name: string; email: string; language: string; opted_out: boolean };
  due: null | { kind: "case" | "request"; id: string; seq?: number; amount_paise: number; due_date: string | null; root_cause: string | null; pending_requests: number; title: string };
  open_case: null | { id: string; seq: number; amount_paise: number; stage: string; status: string; root_cause: string | null; due_date: string };
  promise: null | { promised_date: string; status: string };
  history: { invoice: string; amount_paise: number; status: string; due_date: string; payment_id: string | null; title: string; billing_cycle: string | null }[];
};

export default function CustomerPortal() {
  const router = useRouter();
  const push = useUI((s) => s.push);
  const [me, setMe] = useState<Me | null>(null);
  const [checked, setChecked] = useState(false);
  const [busy, setBusy] = useState("");
  const [replyBox, setReplyBox] = useState("");
  const [note, setNote] = useState<{ tone: "ok" | "warn"; title: string; body: string } | null>(null);

  const load = () => api<Me>("/portal/me").then(setMe).catch(() => router.replace("/portal/login")).finally(() => setChecked(true));
  useEffect(() => { const t = setInterval(() => { void api<Me>("/portal/me").then(setMe).catch(() => {}); }, 4000); return () => clearInterval(t); }, []);
  useEffect(() => { void load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (!checked) return <div className="flex min-h-screen items-center justify-center"><div className="skeleton h-10 w-44" /></div>;
  if (!me) return null;

  async function pay(invoiceId?: string) {
    setBusy(invoiceId ?? "pay");
    try {
      const o = await api<{ order_id: string; amount_paise: number; key_id: string; checkout_live: boolean }>("/portal/order", {
        method: "POST", json: invoiceId ? { invoice_id: invoiceId } : {},
      });
      if (!(o.checkout_live && o.key_id)) {
        router.push(`/pay/${o.order_id}`);
        return;
      }
      // Try to load Razorpay's hosted checkout. In an offline embedded preview the
      // script cannot load — fall back to the app's own capture path (the same
      // service a payment.captured webhook runs), clearly labelled.
      let hosted = false;
      try {
        await new Promise<void>((res, rej) => {
          const s = document.createElement("script");
          s.src = "https://checkout.razorpay.com/v1/checkout.js";
          s.onload = () => res();
          s.onerror = () => rej(new Error("load failed"));
          document.body.appendChild(s);
        });
        hosted = true;
      } catch {
        hosted = false;
      }

      if (!hosted) {
        await api("/portal/checkout", { method: "POST", json: { order_id: o.order_id, test_fallback: true } });
        push("ok", "Payment captured via in-app test capture (hosted checkout unavailable in this environment)");
        void load();
        return;
      }

      const w = window as unknown as { Razorpay: new (o: Record<string, unknown>) => { open: () => void } };
      const rzp = new w.Razorpay({
        key: o.key_id, amount: o.amount_paise, currency: "INR", name: "RecoverPay AI", order_id: o.order_id, theme: { color: "#A99B79" },
        modal: { ondismiss: () => { api(`/payments/${o.order_id}/sync`, { method: "POST", json: {} }).then(() => load()).catch(() => {}); } },
        handler: async (resp: { razorpay_order_id: string; razorpay_payment_id: string; razorpay_signature: string }) => {
          try {
            await api("/portal/checkout", { method: "POST", json: resp });
            push("ok", "Payment received — receipt generated");
            void load();
          } catch (e) { push("err", (e as Error).message); }
        },
      });
      rzp.open();
    } catch (e) {
      push("err", (e as Error).message);
    }
    setBusy("");
  }

  async function reply(text: string) {
    if (!text.trim()) return;
    setBusy("reply");
    try {
      const r = await api<{ intent: string; accepted?: boolean; reject_reason?: string | null; reply_subject: string; reply_body: string }>("/portal/reply", { method: "POST", json: { text } });
      setNote({ tone: r.accepted === false ? "warn" : "ok", title: r.reply_subject, body: r.reply_body });
      setReplyBox("");
      void load();
    } catch (e) {
      push("err", (e as Error).message);
    }
    setBusy("");
  }

  const due = me.due;

  return (
    <main className="mx-auto min-h-screen max-w-xl px-4 py-8">
      <header className="mb-6 flex items-center justify-between">
        <Logo size="lg" />
        <button className="pill pill-mute hover:!text-rose" onClick={async () => { clearSessions(); await api("/portal/logout", { method: "POST" }).catch(() => {}); router.push("/portal/login"); }}>Log out ↩</button>
      </header>

      <FadeIn>
        <div className="card s4 relative overflow-hidden p-7">
          <div aria-hidden className="pointer-events-none absolute -right-10 -top-10 h-40 w-40 rounded-full bg-[#D8C9A3]/[.07] blur-3xl" />
          <div className="text-[11px] font-bold uppercase tracking-[.14em] text-mute">Namaste {me.customer.name.split(" ")[0]}</div>
          {due ? (
            <>
              <motion.div initial={{ scale: 0.94 }} animate={{ scale: 1 }} className="mt-2 text-4xl font-extrabold tracking-tight text-ink">{fmtINR(due.amount_paise)}</motion.div>
              <div className="mt-1.5 text-[13px] font-medium text-brand2">{due.title}</div>
              <div className="mt-1 text-[13px] text-mute">
                {me.customer.language.startsWith("hi") ? "pending hai" : "pending"} · was due {fmtD(due.due_date)}
                {due.root_cause ? <> · {CAUSE_LABEL[due.root_cause] ?? due.root_cause}</> : null}
                {due.kind === "case" ? <> · case #{(due as { seq?: number }).seq}</> : null}
              </div>
              {due.pending_requests > 0 ? (
                <div className="mt-2 text-[12px] text-warn">
                  {due.kind === "case"
                    ? `+ ${due.pending_requests} more pending payment${due.pending_requests > 1 ? "s" : ""}`
                    : `${due.pending_requests} pending payment${due.pending_requests > 1 ? "s" : ""} included above`}
                  {" "}— Pay now settles the oldest first, or pay each one below.
                </div>
              ) : null}
              {me.promise?.status === "pending" ? (
                <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25, duration: 0.45, ease: [0.22,1,0.36,1] }}
                  className="mt-4 rounded-xl border border-[#D9B36A]/25 bg-[#D9B36A]/[.06] px-4 py-3.5">
                  <div className="flex items-center justify-between text-[11px] font-medium uppercase tracking-[.16em] text-[#D9B36A]">
                    <span>Recovery paused · promise active</span>
                    <span className="num-hero text-[13px] font-semibold">{Math.max(0, Math.ceil((new Date(me.promise.promised_date).getTime() - Date.now()) / 86400000))}d left</span>
                  </div>
                  <div className="relative mt-3">
                    <div className="h-[2px] w-full rounded-full bg-white/[.07]" />
                    <motion.div className="absolute left-0 top-0 h-[2px] rounded-full bg-gradient-to-r from-[#D9B36A]/70 to-[#D9B36A]"
                      initial={{ width: 0 }} animate={{ width: `${Math.min(100, Math.max(4, 100 - (Math.max(0, (new Date(me.promise.promised_date).getTime() - Date.now()) / 86400000) / 7) * 100))}%` }}
                      transition={{ duration: 0.9, ease: [0.22,1,0.36,1] }} />
                    <span className="absolute -top-[3px] left-0 h-2 w-2 rounded-full bg-[#D9B36A]" />
                    <span className="absolute -top-[3px] right-0 h-2 w-2 rounded-full border-2 border-[#D9B36A] bg-canvas" />
                  </div>
                  <div className="mt-2 flex justify-between text-[11px] text-dim">
                    <span>today</span>
                    <span>pay by <b className="text-[#D9B36A]">{fmtD(me.promise.promised_date)}</b> · 09:00 IST</span>
                  </div>
                </motion.div>
              ) : null}
              <motion.button whileTap={{ scale: 0.985 }} className="btn-primary mt-5 w-full !py-3.5 !text-base" disabled={Boolean(busy)} onClick={() => pay()}>
                {busy === "pay" ? "Opening Razorpay…" : "Pay now"}
              </motion.button>
              <p className="mt-2 text-center text-[11px] text-dim">Secure checkout by Razorpay · UPI, cards, netbanking</p>
            </>
          ) : (
            <div className="mt-2">
              <div className="text-4xl font-extrabold text-live">₹0</div>
              <div className="mt-1 text-[13px] text-mute">You&apos;re fully settled. 🎉</div>
            </div>
          )}
        </div>
      </FadeIn>

      {due ? (
        <FadeIn delay={0.08}>
          <div className="card mt-4 p-5">
            <h2 className="display text-sm font-bold text-ink">Need more time? <span className="text-[11px] font-medium text-dim">— promise to pay within 7 days</span></h2>
            <p className="mb-3 mt-0.5 text-[12px] text-mute">Up to 7 days — longer holds aren&apos;t possible (enforced in code).</p>
            <textarea className="input min-h-[70px]" value={replyBox} onChange={(e) => setReplyBox(e.target.value)} placeholder="I can pay in 3 days" />
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <button className="btn-ghost !py-2 !text-[12px]" disabled={busy === "reply" || !replyBox.trim()} onClick={() => reply(replyBox)}>Send</button>
              <span className="text-[11px] text-dim">or pick ≤ 7 days:</span>
              <input type="date" className="input !w-auto !py-1.5 !text-[12px]" min={new Date().toISOString().slice(0, 10)}
                max={new Date(Date.now() + 7 * 864e5).toISOString().slice(0, 10)}
                onChange={(e) => e.target.value && reply(`I will pay on ${e.target.value}`)} />
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <button className="btn-ghost !py-1.5 !text-[12px]" disabled={Boolean(busy)} onClick={() => reply("I already paid this")}>I already paid</button>
              <button className="btn-ghost !py-1.5 !text-[12px]" disabled={Boolean(busy)} onClick={() => reply("This charge is not mine")}>Not my charge</button>
              <button className="btn-danger !py-1.5 !text-[12px]" disabled={Boolean(busy)} onClick={async () => {
                await api("/portal/optout", { method: "POST", json: {} });
                push("ok", "You will not be contacted again");
                void load();
              }}>Stop all contact</button>
            </div>
          </div>
        </FadeIn>
      ) : null}

      <AnimatePresence>
        {note ? (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className={`mt-4 rounded-2xl border px-4 py-3 text-[13px] ${note.tone === "warn" ? "border-warn/30 bg-warn/10 text-warn" : "border-live/30 bg-live/10 text-live"}`}>
            <div className="font-bold">{note.title}</div>
            <div className="mt-1 leading-6">{note.body}</div>
          </motion.div>
        ) : null}
      </AnimatePresence>

      <FadeIn delay={0.14}>
        <div className="card mt-4 p-5">
          <h2 className="mb-3 text-sm font-bold text-ink">History</h2>
          {me.history.length === 0 ? <p className="text-[12px] text-dim">No invoices yet.</p> : (
            <div className="space-y-2">
              {me.history.map((h) => (
                <div key={h.invoice} className="flex items-center justify-between rounded-xl border border-line/60 bg-white/[.02] px-3.5 py-2.5">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-[13px] font-semibold text-ink">{fmtINR(h.amount_paise)}</span>
                      {h.billing_cycle ? <Badge tone={h.billing_cycle === "monthly" ? "live" : h.billing_cycle === "yearly" ? "cyan" : "mute"}>{h.billing_cycle === "one_time" ? "ONE-TIME" : h.billing_cycle.toUpperCase()}</Badge> : null}
                    </div>
                    <div className="truncate text-[12px] text-mute">{h.title}</div>
                    <div className="text-[11px] text-dim">due {fmtD(h.due_date)}{h.payment_id ? ` · ${h.payment_id.slice(0, 18)}` : ""}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    {h.status !== "paid" ? (
                      <button className="btn-primary !px-3 !py-1.5 !text-[11px]" disabled={Boolean(busy)}
                        onClick={() => pay(h.invoice)}>{busy === h.invoice ? "Paying…" : "Pay"}</button>
                    ) : null}
                    <Badge tone={h.status === "paid" ? "live" : h.status === "overdue" ? "sla" : "warn"}>{h.status}</Badge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </FadeIn>
      <p className="mt-6 text-center text-[11px] text-dim">Payments by Razorpay · last refreshed {fmtDT(new Date().toISOString())}</p>
    </main>
  );
}
