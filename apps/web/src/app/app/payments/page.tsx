"use client";

import { useState } from "react";
import { api, useApi, fmtINR, fmtDT } from "@/lib/api";
import { Badge, Empty, Skeleton } from "@/components/ui";
import { FadeIn, PageTitle, Stagger, StaggerItem } from "@/lib/motion";
import { useUI } from "@/lib/store";
import { motion, AnimatePresence } from "framer-motion";
import { SuccessCheck, CopyFeedback, EASE } from "@/components/motion";

type Customer = { id: string; name: string; email: string; phone: string; language: string; billing_cycle: string | null; created_at: string };
type Req = { invoice_id: string; order_id: string; amount_paise: number; status: string; customer: string; email: string; created_at: string; case_seq: number | null; case_id: string | null; billing_cycle: string; customer_cycle: string | null; title: string };

const CYCLE_TONE: Record<string, "live" | "cyan" | "mute"> = { monthly: "live", yearly: "cyan", one_time: "mute" };
const CYCLE_LABEL: Record<string, string> = { monthly: "MONTHLY", yearly: "YEARLY", one_time: "ONE-TIME" };

export default function PaymentRequests() {
  const push = useUI((s) => s.push);
  const { data: custData, isLoading: loadingCust } = useApi<{ customers: Customer[] }>(["customers"], "/customers");
  const { data: reqData, isLoading: loadingReq, refetch } = useApi<{ requests: Req[] }>(["requests"], "/payment-requests", { refetchInterval: 4_000, refetchOnWindowFocus: true });

  const [mode, setMode] = useState<"pick" | "new">("pick");
  const [cycle, setCycle] = useState<"monthly" | "yearly" | "one_time">("one_time");
  const [nc, setNc] = useState({ name: "", email: "", phone: "", preferred_language: "en-IN" });
  const [customerId, setCustomerId] = useState("");
  const [amount, setAmount] = useState("");
  const [title, setTitle] = useState("");
  const [note, setNote] = useState("");
  const [channels, setChannels] = useState<Array<"email" | "whatsapp" | "voice">>(["email"]);
  const [whatsappPermission, setWhatsappPermission] = useState(false);
  const [voicePermission, setVoicePermission] = useState(false);
  const [busy, setBusy] = useState(false);
  const [lastLink, setLastLink] = useState<{ link: string; delivered: boolean; queued: boolean; channels: string[] } | null>(null);

  async function send() {
    setBusy(true);
    try {
      let cid = customerId;
      if (mode === "new") {
        const c = await api<{ customer_id: string }>("/customers", { method: "POST", json: { ...nc, billing_cycle: cycle } });
        cid = c.customer_id;
        setCustomerId(cid);
      }
      if (!cid) { push("err", "Pick or create a customer first"); setBusy(false); return; }
      const paise = Math.round(parseFloat(amount.replace(/[₹,\s]/g, "")) * 100);
      if (!paise || paise < 100) { push("err", "Enter a valid amount"); setBusy(false); return; }
      const r = await api<{ link: string; email_delivered: boolean; email_queued: boolean; order_id: string; delivery?: Record<string, { ok: boolean; provider?: string }> }>("/payment-requests", {
        method: "POST", json: { customer_id: cid, amount_paise: paise, title, note: note || null, billing_cycle: cycle, channels, whatsapp_permission: whatsappPermission, voice_permission: voicePermission },
      });
      const delivery = r.delivery ?? {};
      const deliveredChannels = Object.entries(delivery).filter(([, v]) => v.ok).map(([name]) => name === "voice" ? "phone" : name);
      const failedChannels = Object.entries(delivery).filter(([, v]) => !v.ok).map(([name]) => name === "voice" ? "phone" : name);
      setLastLink({ link: r.link, delivered: deliveredChannels.length > 0, queued: r.email_queued, channels });
      if (failedChannels.length === 0) push("ok", `Request created — ${deliveredChannels.join(" + ")} dispatch accepted`);
      else push("err", `Request created, but ${failedChannels.join(" + ")} dispatch failed`);
      setAmount(""); setTitle(""); setNote(""); setChannels(["email"]); setWhatsappPermission(false); setVoicePermission(false);
      refetch();
    } catch (e) { push("err", (e as Error).message); }
    setBusy(false);
  }

  return (
    <div className="space-y-5">
      <PageTitle title="Payment requests" sub="Create a real Razorpay order and email the link. Declines become recovery cases automatically." />
        <FadeIn>
          <div className="card card-edge space-y-4 p-6">
            <div className="flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-brand to-fuchsia text-lg shadow-glow">⚡</span>
              <div>
                <h2 className="display text-base font-bold text-ink">New request</h2>
                <p className="text-[11px] text-dim">real Razorpay order + email with a hosted link · seconds</p>
              </div>
            </div>
            <div className="flex gap-2">
              <button onClick={() => setMode("pick")} className={`pill border ${mode === "pick" ? "border-brand/40 bg-brand/10 text-brand2" : "border-line2 text-mute"}`}>EXISTING</button>
              <button onClick={() => setMode("new")} className={`pill border ${mode === "new" ? "border-brand/40 bg-brand/10 text-brand2" : "border-line2 text-mute"}`}>NEW CUSTOMER</button>
            </div>
            <AnimatePresence mode="wait" initial={false}>
            {mode === "pick" ? (
              <motion.div key="pick" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.22, ease: EASE }}>
                {loadingCust ? <Skeleton className="h-10" /> : (
                  <div>
                    <label className="label">Customer</label>
                    <select className="input" value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
                      <option value="">Select…</option>
                      {(custData?.customers ?? []).map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name} · {c.email}{c.billing_cycle === "monthly" ? " · monthly subscriber" : c.billing_cycle === "yearly" ? " · yearly subscriber" : ""}
                        </option>
                      ))}
                    </select>
                    {(custData?.customers.length ?? 0) === 0 ? <p className="mt-1.5 text-[11px] text-dim">No customers yet — create one.</p> : null}
                  </div>
                )}
              </motion.div>
            ) : (
              <motion.div key="new" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.22, ease: EASE }}>
                <div><label className="label">Name</label><input className="input" value={nc.name} onChange={(e) => setNc({ ...nc, name: e.target.value })} placeholder="Full name" /></div>
                <div className="grid grid-cols-2 gap-2">
                  <div><label className="label">Email</label><input className="input !text-[12px]" value={nc.email} onChange={(e) => setNc({ ...nc, email: e.target.value })} placeholder="customer@email.com" /></div>
                  <div><label className="label">Phone</label><input className="input !text-[12px]" value={nc.phone} onChange={(e) => setNc({ ...nc, phone: e.target.value })} placeholder="+91…" /></div>
                </div>
              </motion.div>
            )}
            </AnimatePresence>
            <div>
              <label className="label">Billing type</label>
              <div className="flex rounded-xl border border-line2 bg-black/30 p-1">
                {(["monthly", "yearly", "one_time"] as const).map((c) => (
                  <button key={c} type="button" onClick={() => setCycle(c)}
                    className={`relative flex-1 rounded-lg px-3 py-1.5 text-[11px] font-bold tracking-wide transition-colors ${cycle === c ? "text-white" : "text-mute hover:text-ink"}`}>
                    {cycle === c && (
                      <motion.span layoutId="cycleSeg" className="absolute inset-0 rounded-lg bg-gradient-to-r from-brand to-fuchsia shadow-glow"
                        transition={{ type: "spring", stiffness: 400, damping: 30 }} />
                    )}
                    <span className="relative">{c === "one_time" ? "ONE-TIME" : c.toUpperCase()}</span>
                  </button>
                ))}
              </div>
              <p className="mt-1.5 text-[11px] text-dim">{cycle === "monthly" ? "Recurring — billed every month" : cycle === "yearly" ? "Recurring — billed once a year" : "One-time settlement — no renewal"}</p>
            </div>
            <div><label className="label">What is it for</label><input className="input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Pro plan — September" /></div>
            <div><label className="label">Amount (₹)</label><input className="input" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="2499" /></div>
            <div><label className="label">Delivery channels</label>
              <div className="grid grid-cols-3 gap-2">
                {([
                  ["email", "✉", "Email", "Direct payment request"],
                  ["whatsapp", "◌", "WhatsApp", "Vonage / Twilio WhatsApp"],
                  ["voice", "◉", "Phone call", "Twilio Voice"],
                ] as const).map(([key, icon, label, text]) => { const active = channels.includes(key); return <button key={key} type="button" onClick={() => setChannels(v => active ? v.filter(x => x !== key) : [...v, key])} className={`relative rounded-xl border p-3 text-left transition-all ${active ? "border-brand2/50 bg-brand/10 shadow-[0_0_24px_-14px_rgba(85,220,255,.65)]" : "border-line2 bg-black/20 hover:border-brand2/25"}`}>
                  <div className="flex items-center gap-2"><span className="text-sm">{icon}</span><span className="text-[11px] font-semibold text-ink">{label}</span><span className={`ml-auto h-3 w-3 rounded-full border ${active ? "border-live bg-live shadow-[0_0_8px_rgba(124,212,180,.65)]" : "border-line2"}`} /></div>
                  <div className="mt-1 text-[9px] leading-4 text-dim">{text}</div>
                </button>; })}
              </div>
              <div className="mt-2 grid gap-2 sm:grid-cols-2">
                {channels.includes("whatsapp") ? <label className="flex items-start gap-2 rounded-lg border border-line/60 bg-white/[.02] p-2.5 text-[10px] text-mute"><input type="checkbox" checked={whatsappPermission} onChange={(e) => setWhatsappPermission(e.target.checked)} className="mt-0.5" /> I confirm the customer has permission for WhatsApp contact.</label> : null}
                {channels.includes("voice") ? <label className="flex items-start gap-2 rounded-lg border border-line/60 bg-white/[.02] p-2.5 text-[10px] text-mute"><input type="checkbox" checked={voicePermission} onChange={(e) => setVoicePermission(e.target.checked)} className="mt-0.5" /> I confirm I have permission to place this recovery call.</label> : null}
              </div>
              <p className="mt-1.5 text-[10px] text-dim">The selected plan is recorded in the audit trail. Email is the default; WhatsApp prefers Vonage when configured; phone uses Twilio when configured and permitted.</p>
            </div>
            <div><label className="label">Note (optional)</label><input className="input" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Thanks for your business!" /></div>
            <button className="btn-primary w-full" disabled={busy || !title || !amount || channels.length === 0 || (channels.includes("whatsapp") && !whatsappPermission) || (channels.includes("voice") && !voicePermission) || (mode === "pick" ? !customerId : !nc.email)} onClick={send}>
              {busy ? "Creating…" : "Create & send request"}
            </button>
            <AnimatePresence>
            {lastLink ? (
              <motion.div key="link" initial={{ opacity: 0, scale: 0.96, y: 8 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.97 }}
                transition={{ type: "spring", stiffness: 300, damping: 24 }}
                className="rounded-2xl border border-lime/25 bg-lime/[.06] p-4">
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.15 }} className="mb-2 flex items-center gap-2 text-[13px] font-semibold text-lime">
                  <SuccessCheck size={16} /> Request created — {lastLink.channels.map(c => c === "voice" ? "phone" : c).join(" + ")} {lastLink.delivered ? "dispatch accepted" : lastLink.queued ? "queued" : "delivery needs attention"}
                </motion.div>
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }} className="mb-2.5 break-all rounded-lg bg-black/30 px-3 py-2 font-mono text-[10px] text-mute">
                  {lastLink.link}
                </motion.div>
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.4 }} className="flex items-center gap-2">
                  <CopyFeedback onCopy={async () => { try { await navigator.clipboard.writeText(lastLink.link); } catch {} }} label="Copy link" />
                  <button className="btn-ghost !py-1.5 !text-[12px]" onClick={() => window.open(lastLink.link)}>Open ↗</button>
                </motion.div>
              </motion.div>
            ) : null}
            </AnimatePresence>
          </div>
        </FadeIn>

        <FadeIn delay={0.08}>
          <div className="card p-5">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-sm font-bold text-ink">Recent requests</h2>
              <div className="flex items-center gap-3">
                <span className="flex items-center gap-1.5 text-[11px] text-dim"><span className="relative flex h-1.5 w-1.5"><span className="absolute h-1.5 w-1.5 animate-ping rounded-full bg-live/60" /><span className="h-1.5 w-1.5 rounded-full bg-live" /></span>live · auto-syncs every 10s</span>
                <button className="btn-ghost !py-1.5 !text-[11px]" onClick={async () => {
                  try { const s = await api<{ captured: number }>("/payments/sync-all", { method: "POST", json: {} }); push(s.captured ? "ok" : "info", s.captured ? `${s.captured} new payment(s) captured` : "Up to date"); refetch(); } catch (e) { push("err", (e as Error).message); }
                }}>Sync now</button>
              </div>
            </div>
            {loadingReq ? (
              <div className="space-y-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-14" />)}</div>
            ) : !reqData || reqData.requests.length === 0 ? (
              <Empty title="No payment requests yet" body="Create your first one on the left — the customer receives a real Razorpay checkout link." />
            ) : (
              <Stagger gap={0.04} className="space-y-2">
                {reqData.requests.map((r) => (
                  <StaggerItem key={r.invoice_id}>
                    <motion.div whileHover={{ x: 3 }} transition={{ type: "spring", stiffness: 300, damping: 20 }} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line/60 bg-white/[.02] px-4 py-3 hover:border-brand2/30">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-[13px] font-semibold text-ink">{r.customer}</span>
                          <Badge tone={CYCLE_TONE[r.billing_cycle] ?? "mute"}>{CYCLE_LABEL[r.billing_cycle] ?? r.billing_cycle}</Badge>
                          <span className="text-[13px] font-bold text-brand2">{fmtINR(r.amount_paise)}</span>
                          <Badge tone={r.status === "paid" ? "live" : r.status === "failed" ? "sla" : "warn"}>{r.status}</Badge>
                          {r.case_seq ? <a href={`/app/cases/${r.case_id}`} className="pill bg-brand/10 text-brand2 ring-1 ring-brand/25 hover:underline">case #{r.case_seq}</a> : null}
                        </div>
                        <div className="truncate text-[12px] text-mute">{r.title}</div>
                        <div className="truncate text-[11px] text-dim">{r.order_id} · {fmtDT(r.created_at)}</div>
                      </div>
                      <button className="btn-ghost !py-1.5 !text-[11px]" onClick={async () => {
                        try {
                          const s = await api<{ synced: boolean; result?: string; message?: string }>(`/payments/${r.order_id}/sync`, { method: "POST", json: {} });
                          push(s.synced ? "ok" : "info", s.message ?? `Synced: ${s.result}`);
                          refetch();
                        } catch (e) { push("err", (e as Error).message); }
                      }}>Sync status</button>
                    </motion.div>
                  </StaggerItem>
                ))}
              </Stagger>
            )}
          </div>
        </FadeIn>

      <FadeIn delay={0.18}>
        <div className="card p-5">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-bold text-ink">Customers</h2>
            <span className="text-[11px] text-dim">saved records · updated on every new request</span>
          </div>
          {loadingCust ? <Skeleton className="h-12" /> : (custData?.customers.length ?? 0) === 0 ? (
            <p className="text-[12px] text-dim">No customers yet.</p>
          ) : (
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {custData!.customers.map((c) => (
                <div key={c.id} className="rounded-xl border border-line/60 bg-white/[.02] px-3.5 py-2.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-[13px] font-semibold text-ink">{c.name}</span>
                    <Badge tone={CYCLE_TONE[c.billing_cycle ?? "one_time"] ?? "mute"}>{CYCLE_LABEL[c.billing_cycle ?? "one_time"]}</Badge>
                  </div>
                  <div className="truncate text-[11px] text-dim">{c.email} · {c.phone}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </FadeIn>

    </div>
  );
}
