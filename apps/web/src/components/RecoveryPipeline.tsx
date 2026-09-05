"use client";

import { motion } from "framer-motion";
import { fmtINR } from "@/lib/api";

export type RecoveryStage = {
  key: string;
  label: string;
  value?: number;
  state?: "done" | "active" | "idle";
};

export function RecoveryPipeline({ stages, compact = false }: { stages: RecoveryStage[]; compact?: boolean }) {
  return (
    <div className={compact ? "rounded-2xl border border-line/60 bg-white/[.015] p-4" : "card card-edge p-5"}>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[.2em] text-dim">Recovery lifecycle</div>
          <div className="mt-1 text-[12px] text-mute">State moves only when the agent or payment system produces an event.</div>
        </div>
        <span className="pill pill-brand">DETECT → RECOVER</span>
      </div>
      <div className="relative">
        <div className="absolute left-[5%] right-[5%] top-3 h-px bg-white/[.08]" />
        <div className="grid grid-cols-5 gap-2">
          {stages.map((s, i) => (
            <div key={s.key} className="relative flex min-w-0 flex-col items-center text-center">
              <div className="relative z-10 flex h-6 w-6 items-center justify-center rounded-full border border-white/[.1] bg-[#0b0d12]">
                <motion.span
                  className={`h-2 w-2 rounded-full ${s.state === "done" ? "bg-lime shadow-[0_0_12px_rgba(124,212,180,.55)]" : s.state === "active" ? "bg-[#D8C9A3] shadow-[0_0_12px_rgba(216,201,163,.5)]" : "bg-[#3A3D4C]"}`}
                  animate={s.state === "active" ? { scale: [1, 1.25, 1] } : { scale: 1 }}
                  transition={{ duration: 1.8, repeat: s.state === "active" ? Infinity : 0 }}
                />
              </div>
              <div className="mt-2 truncate text-[9px] font-semibold uppercase tracking-[.15em] text-dim">{s.label}</div>
              {s.value !== undefined ? <div className="mt-1 num-hero text-[11px] font-semibold text-ink">{fmtINR(s.value)}</div> : null}
              {i < stages.length - 1 && s.state === "done" ? (
                <motion.span className="absolute left-[55%] right-[-45%] top-3 h-px origin-left bg-gradient-to-r from-lime/50 to-transparent" initial={{ scaleX: 0 }} animate={{ scaleX: 1 }} transition={{ delay: i * .1, duration: .5 }} />
              ) : null}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function DecisionTrace({ recommendation, checks, allowed, action }: {
  recommendation: string; checks: Record<string, unknown>; allowed: boolean; action: string;
}) {
  const entries = Object.entries(checks).filter(([k]) => ["opted_out", "quiet_hours_ist", "attempts", "cap", "est_cost_paise", "missing_consent", "promise_until"].includes(k));
  return (
    <div className="card s3 p-5">
      <div className="mb-4 flex items-start justify-between">
        <div><div className="text-[10px] font-semibold uppercase tracking-[.2em] text-dim">Decision trace</div><h3 className="mt-1 text-sm font-bold text-ink">AI proposes. Policy decides.</h3></div>
        <span className={`pill ${allowed ? "pill-live" : "pill-sla"}`}>{allowed ? "ACTION APPROVED" : "ACTION BLOCKED"}</span>
      </div>
      <div className="grid gap-3 md:grid-cols-[1fr_auto_1fr_auto_1fr] md:items-center">
        <div className="rounded-xl border border-brand2/20 bg-brand/5 p-3">
          <div className="text-[9px] uppercase tracking-[.18em] text-dim">AI recommendation</div>
          <div className="mt-1 text-sm font-semibold text-ink">{recommendation}</div>
        </div>
        <div className="text-center text-dim">→</div>
        <div className="rounded-xl border border-warn/20 bg-warn/5 p-3">
          <div className="text-[9px] uppercase tracking-[.18em] text-dim">Policy engine</div>
          <div className="mt-1 text-sm font-semibold text-ink">{entries.length ? `${entries.length} guardrails evaluated` : "Guardrails evaluated"}</div>
        </div>
        <div className="text-center text-dim">→</div>
        <div className={`rounded-xl border p-3 ${allowed ? "border-live/20 bg-live/5" : "border-sla/20 bg-sla/5"}`}>
          <div className="text-[9px] uppercase tracking-[.18em] text-dim">Final action</div>
          <div className="mt-1 text-sm font-semibold text-ink">{action.replaceAll("_", " ")}</div>
        </div>
      </div>
      {entries.length ? (
        <div className="mt-4 flex flex-wrap gap-2 border-t border-line/60 pt-3">
          {entries.map(([key, value]) => (
            <span key={key} className="pill pill-mute"><span className="text-dim">{key.replaceAll("_", " ")}</span><b className="text-ink">{String(value)}</b></span>
          ))}
        </div>
      ) : null}
    </div>
  );
}
