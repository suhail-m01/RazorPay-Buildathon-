"use client";

import { useState } from "react";
import { api, useApi, fmtINR } from "@/lib/api";
import { Badge, Empty, Skeleton, Stat } from "@/components/ui";
import { CountUp, FadeIn, PageTitle, Stagger, StaggerItem, motion } from "@/lib/motion";
import { useUI } from "@/lib/store";
import { CauseBar } from "@/components/merchant/Charts";

type Report = {
  tag: string; cases: number; at_risk_paise: number; recovered_cases: number; recovered_paise: number;
  recovery_rate: number; baseline_rate: number; baseline_paise: number; uplift_pct_points: number;
  extra_vs_naive_paise: number; cost_paise: number; cost_per_100_recovered_paise: number;
  by_root_cause: Record<string, { cases: number; recovered: number; amount_paise: number }>;
  by_channel: Record<string, { cases: number; recovered: number }>;
  promises: { kept: number; broken: number; pending: number; rejected: number };
  avg_recovery_hours?: number;
  funnel?: Record<string, number>;
};

export default function BatchPage() {
  const push = useUI((s) => s.push);
  const [size, setSize] = useState(40);
  const [busy, setBusy] = useState(false);
  const [tag, setTag] = useState<string | null>(null);
  const { data, isLoading, refetch } = useApi<Report>(["batch", tag], `/batch/report${tag ? `?tag=${tag}` : ""}`);

  async function run() {
    setBusy(true);
    try {
      const r = await api<{ tag: string; size: number; outcomes: Record<string, number>; report: Report }>("/batch/run", {
        method: "POST", json: { size },
      });
      setTag(r.tag);
      push("ok", `Batch ${r.tag}: ${r.size} cases run through the real agent`);
      refetch();
    } catch (e) { push("err", (e as Error).message); }
    setBusy(false);
  }

  const r = data;

  return (
    <div className="space-y-5">
      <PageTitle title="Recovery batches" sub="A labeled cohort (@example.test, send-gated) pushed through the REAL agent — diagnosis, policy gates, promises, captures — measured honestly.">
        <div className="flex items-center gap-2">
          <select className="input !w-24 !py-2 !text-[12px]" value={size} onChange={(e) => setSize(Number(e.target.value))}>
            {[20, 40, 60, 100].map((n) => <option key={n} value={n}>{n} cases</option>)}
          </select>
          <button className="btn-primary !py-2" disabled={busy} onClick={run}>{busy ? "Running agent…" : "Run batch"}</button>
        </div>
      </PageTitle>

      <FadeIn>
        <div className="card border-brand/20 bg-brand/[.04] p-4 text-[12px] leading-5 text-mute">
          <b className="text-ink">Honest by design:</b> contacts are synthetic and every send is gate-simulated, but the engine is
          the production one — root-cause diagnosis, quiet hours, consent, attempt caps, the 7-day promise rule and the capture
          path all execute for real. Dashboard analytics exclude batch rows.
        </div>
      </FadeIn>

      {isLoading ? (
        <div className="grid gap-3 sm:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-28" />)}</div>
      ) : !r ? (
        <Empty title="No batches yet" body="Run one — you'll get measured money recovered, uplift vs a naive-retry baseline, cost-to-recover and per-cause recovery rates." />
      ) : (
        <>
          <Stagger className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StaggerItem><Stat label="Money recovered" tone="live" value={<CountUp value={r.recovered_paise / 100} format={(n) => fmtINR(n * 100)} />} sub={`${r.recovered_cases}/${r.cases} cases across the batch`} /></StaggerItem>
            <StaggerItem><Stat label="Recovery rate" tone="brand" value={<CountUp value={r.recovery_rate * 100} format={(n) => `${n.toFixed(1)}%`} />} sub={`naive single-channel baseline: ${(r.baseline_rate * 100).toFixed(0)}%`} /></StaggerItem>
            <StaggerItem><Stat label="Uplift vs naive" tone="sla" value={`+${r.uplift_pct_points}pp`} sub={`${fmtINR(Math.max(0, r.extra_vs_naive_paise))} extra recovered`} /></StaggerItem>
            <StaggerItem><Stat label="Cost to recover" tone="warn" value={`₹${(r.cost_paise / 100).toFixed(2)}`} sub={`₹${r.cost_per_100_recovered_paise.toFixed(2)} per ₹100 recovered`} /></StaggerItem>
          </Stagger>

          <FadeIn delay={0.07}>
            <div className="card p-5">
              <div className="mb-4 flex items-center justify-between"><div><h2 className="display text-sm font-bold text-ink">Batch recovery outcome</h2><p className="text-[11px] text-dim">Money is the primary proof point; operational counts explain the funnel.</p></div><Badge tone="live">THE BAR</Badge></div>
              <div className="grid gap-3 sm:grid-cols-4">
                {[
                  ["Revenue at risk", fmtINR(r.at_risk_paise), "exposure"],
                  ["AI processed", `${r.funnel?.diagnose ?? r.cases}`, "diagnosed by agent"],
                  ["Recovered", fmtINR(r.recovered_paise), `${r.recovered_cases} cases`],
                  ["Net after cost", fmtINR(Math.max(0, r.recovered_paise-r.cost_paise)), `${((r.recovered_paise/Math.max(1,r.cost_paise))).toFixed(1)}× gross/cost`],
                ].map(([a,b,c])=><div key={a} className="rounded-xl border border-line/60 bg-white/[.02] p-4"><div className="text-[9px] uppercase tracking-[.18em] text-dim">{a}</div><div className="mt-1 num-hero text-xl font-semibold text-ink">{b}</div><div className="mt-1 text-[10px] text-mute">{c}</div></div>)}
              </div>
              <div className="mt-4 grid grid-cols-5 gap-1">
                {[["Detected",r.funnel?.case_detected ?? r.cases],["Diagnosed",r.funnel?.diagnose ?? r.cases],["Actioned",r.cases-r.promises.rejected],["Promise",r.promises.kept+r.promises.pending],["Recovered",r.recovered_cases]].map(([a,n])=><div key={a} className="rounded-lg bg-white/[.025] p-2 text-center"><div className="num-hero text-sm font-semibold text-ink">{n}</div><div className="mt-1 text-[9px] uppercase tracking-wider text-dim">{a}</div></div>)}
              </div>
            </div>
          </FadeIn>

          <div className="grid gap-5 lg:grid-cols-2">
            <FadeIn delay={0.08}>
              <div className="card p-5">
                <h2 className="display mb-1 text-sm font-bold text-ink">Recovery by root cause</h2>
                <p className="mb-3 text-[11px] text-dim">green = recovered, indigo = still open/stopped</p>
                <CauseBar data={Object.entries(r.by_root_cause).map(([cause, v]) => ({
                  cause: cause.replaceAll("_", " ").slice(0, 14),
                  recovered: v.recovered, open: v.cases - v.recovered,
                }))} />
              </div>
            </FadeIn>
            <FadeIn delay={0.12}>
              <div className="card p-5">
                <h2 className="display mb-3 text-sm font-bold text-ink">Which channel recovered the money</h2>
                <div className="space-y-2.5">
                  {Object.entries(r.by_channel).sort((a, b) => b[1].recovered - a[1].recovered).map(([ch, v]) => (
                    <div key={ch}>
                      <div className="mb-1 flex justify-between text-[12px]"><span className="capitalize text-mute">{ch}</span><span className="font-semibold text-ink">{v.recovered}/{v.cases}</span></div>
                      <div className="h-2 overflow-hidden rounded-full bg-white/5">
                        <motion.div initial={{ width: 0 }} animate={{ width: `${(v.recovered / v.cases) * 100}%` }} transition={{ duration: 0.8 }}
                          className="h-full rounded-full bg-gradient-to-r from-brand to-cyan" />
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mt-4 flex flex-wrap gap-2 border-t border-line/60 pt-3 text-[11px]">
                  <Badge tone="live">promises kept {r.promises.kept}</Badge>
                  <Badge tone="sla">broken {r.promises.broken}</Badge>
                  <Badge tone="warn">refused &gt;7d {r.promises.rejected}</Badge>
                </div>
              </div>
            </FadeIn>
          </div>
        </>
      )}
    </div>
  );
}
