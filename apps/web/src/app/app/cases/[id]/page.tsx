"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, useApi, fmtINR, fmtDT, STAGE_LABEL, CAUSE_LABEL } from "@/lib/api";
import { Badge, LivePill, Skeleton, riskTone, stageTone, statusTone } from "@/components/ui";
import { AnimatePresence, FadeIn, motion, PageTitle } from "@/lib/motion";
import { TimelineLine, TimelineNode, EASE, AnimatedStatus, SuccessCheck, RiskRing, PulseDot } from "@/components/motion";
import { CaseActions } from "@/components/merchant/actions";
import { RecoveryPipeline, DecisionTrace } from "@/components/RecoveryPipeline";
import { useUI } from "@/lib/store";
import clsx from "clsx";

type Detail = {
  case: { seq: number; type: string; amount_paise: number; risk_score: number; root_cause: string | null; confidence: number; stage: string; status: string; attempts: number; failure_reason_code: string | null; stop_reason: string | null; created_at: string };
  voice_script: string | null;
  customer: { name: string; email: string; phone: string; preferred_channel: string; preferred_language: string; consents: Record<string, boolean>; opted_out: boolean; is_demo_contact: boolean };
  invoice: { amount_paise: number; status: string; due_date: string; order_id?: string; title?: string; billing_cycle?: string | null };
  timeline: { id: number; actor: string; action: string; reason_code: string | null; channel: string | null; message: string | null; simulated: boolean; checks: Record<string, unknown> | null; ts: string }[];
  promises: { id: string; promised_date: string; status: string; reject_reason: string | null; utterance: string }[];
};

export default function CaseDetail({ params }: { params: { id: string } }) {
  const id = String(useParams()["id"]);
  const push = useUI((s) => s.push);
  const { data, isLoading, refetch } = useApi<Detail>(["case", id], `/cases/${id}`, { refetchInterval: 10_000 });
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);

  if (isLoading || !data) return <div className="space-y-4"><Skeleton className="h-24" /><Skeleton className="h-64" /></div>;
  const c = data.case;

  const sendReply = async (text: string) => {
    if (!text.trim()) return;
    setBusy(true);
    try {
      const r = await api<{ reply_subject: string; reply_body: string; accepted?: boolean; reject_reason?: string }>(`/cases/${id}/reply-as`, { method: "POST", json: { text } });
      push(r.accepted === false ? "info" : "ok", `${r.reply_subject} — ${r.reject_reason ?? "logged to timeline"}`);
      setReply("");
      refetch();
    } catch (e) { push("err", (e as Error).message); }
    setBusy(false);
  };

  return (
    <div className="space-y-5">
      <PageTitle title={`Case #${c.seq} · ${data.customer.name}`} sub={`Diagnosed as ${CAUSE_LABEL[c.root_cause ?? ""] ?? c.root_cause} with ${(c.confidence * 100).toFixed(0)}% confidence`}>
        <div className="flex items-center gap-2">
          <LivePill live={data.customer.is_demo_contact} />
          <span className="flex items-center gap-1.5"><RiskRing score={c.risk_score} size={34} /><span className="text-[10px] font-medium uppercase tracking-[.18em] text-dim">risk</span></span>
          <Badge tone={stageTone(c.stage)}><AnimatedStatus status={STAGE_LABEL[c.stage] ?? c.stage} /></Badge>
          {c.status === "recovered" ? (
  <span className="pill pill-live"><SuccessCheck size={12} /> RECOVERED</span>
) : <Badge tone={statusTone(c.status)}><AnimatedStatus status={c.status} /></Badge>}
        </div>
      </PageTitle>

      <FadeIn delay={0.04}>
        <RecoveryPipeline compact stages={[
          {key:"detect",label:"Detect",state:"done"},
          {key:"diagnose",label:"Diagnose",state:c.stage === "detected" ? "active" : "done"},
          {key:"decide",label:"Decide",state:["detected","diagnosed"].includes(c.stage) ? "active" : "done"},
          {key:"act",label:"Act",state:["detected","diagnosed"].includes(c.stage) ? "idle" : c.status === "open" ? "active" : "done"},
          {key:"recover",label:"Recover",value:c.status === "recovered" ? c.amount_paise : undefined,state:c.status === "recovered" ? "done" : "idle"},
        ]}/>
      </FadeIn>

      {c.status === "recovered" ? (
        <FadeIn delay={0.06}>
          <div className="relative overflow-hidden rounded-2xl border border-live/20 bg-gradient-to-r from-live/[.07] to-transparent p-5">
            <div className="relative flex flex-wrap items-center justify-between gap-5">
              <div><div className="text-[10px] font-semibold uppercase tracking-[.2em] text-live">Payment recovered</div>
                <div className="mt-1 num-hero text-4xl font-semibold text-ink">{fmtINR(c.amount_paise)}</div>
                <div className="mt-1 text-[12px] text-mute">The payment capture path closed this recovery case.</div></div>
              <div className="grid grid-cols-2 gap-2 text-center">
                <div className="rounded-xl border border-line/60 bg-black/10 px-4 py-3"><div className="text-[9px] uppercase tracking-wider text-dim">Attempts</div><div className="num-hero mt-1 text-lg font-semibold text-ink">{c.attempts}</div></div>
                <div className="rounded-xl border border-line/60 bg-black/10 px-4 py-3"><div className="text-[9px] uppercase tracking-wider text-dim">Outcome</div><div className="mt-1 text-sm font-semibold text-live">Captured</div></div>
              </div>
            </div>
          </div>
        </FadeIn>
      ) : null}

      <div className="grid gap-5 lg:grid-cols-3">
        <div className="space-y-5 lg:col-span-2">
          <FadeIn>
            <div className="card p-5">
              <div className="grid gap-4 sm:grid-cols-4">
                <div className="sm:col-span-2"><div className="label !mb-0.5">For</div><div className="text-sm font-semibold text-ink">{data.invoice.title}</div>{data.invoice.billing_cycle ? <div className="text-[11px] text-dim">{data.invoice.billing_cycle.replaceAll("_", "-")}</div> : null}</div>
                <div><div className="label !mb-0.5">Amount</div><div className="text-xl font-bold text-ink">{fmtINR(c.amount_paise)}</div></div>
                <div><div className="label !mb-0.5">Failure code</div><div className="mt-1 font-mono text-[12px] text-mute">{c.failure_reason_code ?? "—"}</div></div>
                <div><div className="label !mb-0.5">Attempts</div><div className="mt-1 text-sm font-semibold text-ink">{c.attempts}/3</div></div>
                <div><div className="label !mb-0.5">Opened</div><div className="mt-1 text-[12px] text-mute">{fmtDT(c.created_at)}</div></div>
              </div>
              {c.stop_reason ? <div className="mt-4 rounded-xl border border-sla/25 bg-sla/5 px-3 py-2 text-[12px] text-sla">Stopped: {c.stop_reason}</div> : null}
            </div>
          </FadeIn>

          {(() => {
            const diagnosis = data.timeline.find((t) => t.action === "diagnose");
            const blocked = data.timeline.find((t) => t.action.endsWith("_blocked"));
            const executed = data.timeline.find((t) => ["send_email","send_whatsapp","send_sms","place_voice_call","retry_payment"].includes(t.action));
            const decision = blocked ?? executed;
            if (!decision && !diagnosis) return null;
            const recommendation = executed ? executed.action.replace("send_","").replace("place_","").replace("retry_","").toUpperCase() : "PENDING";
            const checks = (decision?.checks ?? {}) as Record<string, unknown>;
            return <FadeIn delay={0.07}>
              <div className="space-y-3">
                {diagnosis ? <div className="card p-5">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div><div className="text-[10px] font-semibold uppercase tracking-[.2em] text-dim">AI diagnosis</div>
                      <h2 className="mt-1 text-sm font-bold text-ink">{CAUSE_LABEL[c.root_cause ?? ""] ?? c.root_cause ?? "Pending diagnosis"}</h2>
                      <p className="mt-1 text-[12px] text-mute">{String(diagnosis.checks?.notes ?? "Evidence recorded in the audit trace.")}</p></div>
                    <div className="text-right"><div className="num-hero text-2xl font-semibold text-ink">{Math.round(c.confidence*100)}%</div><div className="text-[9px] uppercase tracking-wider text-dim">confidence</div></div>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2"><Badge tone="brand">{String(diagnosis.checks?.engine ?? "rules")}</Badge>{diagnosis.checks?.evidence ? <Badge tone="mute">{String(diagnosis.checks.evidence)}</Badge> : null}</div>
                </div> : null}
                {decision ? <DecisionTrace recommendation={recommendation} checks={checks} allowed={!blocked} action={decision.action}/> : null}
              </div>
            </FadeIn>;
          })()}

          <FadeIn delay={0.08}>
            <div className="card p-5">
              <h2 className="mb-4 text-sm font-bold text-ink">Action timeline</h2>
              <div className="relative space-y-4">
                <TimelineLine />
                <AnimatePresence initial={false}>
                  {data.timeline.map((t, ti) => (
                    <motion.div key={t.id} layout initial={{ opacity: 0, x: -14 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: Math.min(ti * 0.07, 0.5), duration: 0.4, ease: EASE }}
                      className="relative pl-8">
                      <TimelineNode delay={Math.min(ti * 0.07, 0.5)} latest={ti === 0} tone={t.action.includes("captured") ? "live" : t.action.includes("blocked") ? "sla" : t.action.includes("promise") ? "warn" : "brand"} />
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={clsx("text-[13px] font-semibold", ti === 0 ? "text-ink" : "text-ink/90")}>{t.action.replaceAll("_", " ")}</span>
                        <Badge tone={t.simulated ? "mute" : "live"}>{t.simulated ? "simulated" : "real"}</Badge>
                        {t.channel ? <span className="text-[11px] uppercase text-dim">{t.channel}</span> : null}
                        <span className="text-[11px] text-dim">· {t.actor}</span>
                        <span className="ml-auto text-[11px] text-dim">{fmtDT(t.ts)}</span>
                      </div>
                      {t.reason_code ? <div className="mt-0.5 font-mono text-[11px] text-brand2">{t.reason_code}</div> : null}
                      {t.message ? <div className="mt-1 line-clamp-2 rounded-lg bg-white/[.02] px-3 py-2 text-[12px] leading-5 text-mute">{t.message}</div> : null}
                      {t.checks ? (
                        <details className="mt-1"><summary className="cursor-pointer text-[10px] uppercase tracking-wider text-dim hover:text-mute">compliance checks</summary>
                          <pre className="mt-1 overflow-auto rounded-lg bg-black/40 p-2.5 text-[10px] leading-4 text-mute">{JSON.stringify(t.checks, null, 1)}</pre>
                        </details>
                      ) : null}
                    </motion.div>
                  ))}
                </AnimatePresence>
              </div>
            </div>
          </FadeIn>

          <FadeIn delay={0.12}>
            <div className="card p-5">
              <h2 className="mb-1 text-sm font-bold text-ink">Log a customer response</h2>
              <p className="mb-3 text-[12px] text-mute">Runs the exact promise engine the portal and email replies use — try “3 din baad” vs “next month”.</p>
              <textarea className="input min-h-[72px]" value={reply} onChange={(e) => setReply(e.target.value)} placeholder="I can pay in 3 days" />
              <div className="mt-2 flex flex-wrap gap-2">
                <button className="btn-primary !py-2" disabled={busy || !reply.trim()} onClick={() => sendReply(reply)}>Send reply</button>
                {["I will pay in 3 days", "next month please", "payment ho gaya tha", "stop contacting me"].map((s) => (
                  <button key={s} className="btn-ghost !py-1.5 !text-[12px]" disabled={busy} onClick={() => sendReply(s)}>{s}</button>
                ))}
              </div>
            </div>
          </FadeIn>
        </div>

        <div className="space-y-5">
          <FadeIn delay={0.06}>
            <div className="card p-5">
              <h2 className="mb-3 text-sm font-bold text-ink">Customer</h2>
              <dl className="space-y-2 text-[13px]">
                <div className="flex justify-between"><dt className="text-mute">Email</dt><dd className="text-ink">{data.customer.email}</dd></div>
                <div className="flex justify-between"><dt className="text-mute">Phone</dt><dd className="text-ink">{data.customer.phone}</dd></div>
                <div className="flex justify-between"><dt className="text-mute">Language</dt><dd className="text-ink">{data.customer.preferred_language}</dd></div>
                <div className="flex justify-between"><dt className="text-mute">Opted out</dt><dd className={data.customer.opted_out ? "font-bold text-sla" : "text-mute"}>{data.customer.opted_out ? "YES" : "no"}</dd></div>
                {Object.entries(data.customer.consents).map(([ch, ok]) => (
                  <div key={ch} className="flex justify-between"><dt className="text-mute">{ch} consent</dt><dd className={ok ? "text-live" : "text-dim"}>{ok ? "yes" : "no"}</dd></div>
                ))}
              </dl>
            </div>
          </FadeIn>

          <FadeIn delay={0.1}><div className="card p-5"><h2 className="mb-3 text-sm font-bold text-ink">Agent actions</h2><CaseActions caseId={id} stage={c.stage} status={c.status} /></div></FadeIn>

          {(c.type === "mandate_failed" || c.type === "subscription_failed") ? (
            <FadeIn delay={0.12}>
              <div className="card p-5">
                <h2 className="mb-1 text-sm font-bold text-ink">Mandate retry sequencer</h2>
                <p className="mb-3 text-[12px] text-mute">Mints a fresh Razorpay order so the charge can be re-attempted — also runs automatically every 24h (max 2).</p>
                <button className="btn-ghost w-full !py-2" disabled={busy} onClick={async () => {
                  setBusy(true);
                  try {
                    const r = await api<{ ok: boolean; attempt?: number; blocked?: string }>(`/cases/${id}/retry`, { method: "POST", json: {} });
                    push(r.ok ? "ok" : "info", r.ok ? `Retry #${r.attempt} scheduled (fresh order minted)` : `Blocked: ${r.blocked}`);
                    refetch();
                  } catch (e) { push("err", (e as Error).message); }
                  setBusy(false);
                }}>Retry charge now</button>
              </div>
            </FadeIn>
          ) : null}

          {data.voice_script ? (
            <FadeIn delay={0.14}>
              <div className="card p-5">
                <div className="mb-1 flex items-center justify-between">
                  <h2 className="text-sm font-bold text-ink">Voice call — script</h2>
                  <Badge tone="cyan">{data.customer.preferred_language}</Badge>
                </div>
                <p className="mb-3 text-[12px] text-mute">Final rung (Hinglish default). Play it, log what the customer said.</p>
                <div className="rounded-xl border border-line/70 bg-white/[.02] p-3 text-[12px] leading-6 text-mute">{data.voice_script}</div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button className="btn-ghost !py-1.5 !text-[12px]" onClick={() => {
                    try {
                      const u = new SpeechSynthesisUtterance(data.voice_script ?? "");
                      u.lang = data.customer.preferred_language;
                      window.speechSynthesis.speak(u);
                    } catch { push("err", "Speech synthesis unavailable here"); }
                  }}>▶ Play script</button>
                  {["haan, 3 din baad kar dunga", "payment ho gaya tha", "mat karo call"].map((s) => (
                    <button key={s} className="btn-ghost !py-1.5 !text-[12px]" disabled={busy} onClick={() => sendReply(s)}>{s}</button>
                  ))}
                </div>
              </div>
            </FadeIn>
          ) : null}

          {data.promises.length ? (
            <FadeIn delay={0.14}>
              <div className="card p-5">
                <h2 className="mb-3 text-sm font-bold text-ink">Promises</h2>
                <div className="space-y-2">
                  {data.promises.map((p) => (
                    <div key={p.id} className="rounded-lg border border-line/70 bg-white/[.02] p-2.5 text-[12px]">
                      <div className="flex items-center justify-between">
                        <Badge tone={p.status === "pending" ? "warn" : p.status === "kept" ? "live" : "sla"}>{p.status}</Badge>
                        <span className="text-dim">{fmtDT(p.promised_date)}</span>
                      </div>
                      <div className="mt-1 italic text-mute">“{p.utterance.slice(0, 80)}”</div>
                      {p.status === "pending" ? (
                        <div className="mt-2 h-[3px] w-32 overflow-hidden rounded-full bg-white/[.06]">
                          <motion.div className="h-full rounded-full bg-[#D9B36A]" initial={{ width: 0 }}
                            animate={{ width: `${Math.min(100, Math.max(4, 100 - (Math.max(0, (new Date(p.promised_date).getTime() - Date.now()) / 86400000) / 7) * 100))}%` }}
                            transition={{ duration: 0.8, ease: EASE }} />
                        </div>
                      ) : null}
                      {p.reject_reason ? <div className="mt-1 text-sla">refused: {p.reject_reason}</div> : null}
                    </div>
                  ))}
                </div>
              </div>
            </FadeIn>
          ) : null}
        </div>
      </div>
      <Link href="/app/cases" className="inline-block text-[13px] text-mute hover:text-ink">← back to queue</Link>
    </div>
  );
}
