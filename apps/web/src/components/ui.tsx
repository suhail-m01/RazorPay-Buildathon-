"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useUI } from "@/lib/store";
import { GlowCard } from "@/components/motion";
import clsx from "clsx";

export function Logo({ size = "base" }: { size?: "base" | "lg" }) {
  return (
    <span className={clsx("display font-bold tracking-tight", size === "lg" ? "text-2xl" : "text-lg")}>
      <span className="grad-text">Recover</span>
      <span className="text-ink">Pay</span>
      <span className="ml-1.5 rounded-md bg-white/[.06] px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-[.22em] text-mute align-middle">AI</span>
    </span>
  );
}

export function LivePill({ live }: { live: boolean }) {
  return live ? (
    <span className="pill pill-live"><span className="dot-live" /> LIVE</span>
  ) : (
    <span className="pill pill-warn"><span className="dot-live" style={{ background: "#FBBF24", boxShadow: "0 0 10px 1px rgba(251,191,36,.7)" }} /> TEST</span>
  );
}

export function Badge({ tone = "mute", children, title }: { tone?: "live" | "brand" | "warn" | "sla" | "mute" | "cyan"; children: React.ReactNode; title?: string }) {
  return <span className={clsx("pill", `pill-${tone}`)} title={title}>{children}</span>;
}

export function riskTone(score: number): "sla" | "warn" | "brand" {
  return score >= 70 ? "sla" : score >= 40 ? "warn" : "brand";
}

export function statusTone(status: string): "live" | "brand" | "escalated" extends never ? never : "live" | "brand" | "warn" | "sla" | "mute" {
  return { open: "brand", recovered: "live", escalated: "warn", stopped: "sla", closed: "mute" }[status] as "brand";
}

export function stageTone(stage: string): "live" | "brand" | "warn" | "sla" | "cyan" {
  if (stage === "recovered") return "live";
  if (stage === "escalated" || stage === "stopped" || stage === "closed") return "sla";
  if (stage === "promise_wait") return "warn";
  if (stage === "whatsapp_sent" || stage === "voice_attempted" || stage === "sms_sent") return "cyan";
  return "brand";
}

export function Skeleton({ className = "h-4 w-full" }: { className?: string }) {
  return <div className={clsx("skeleton", className)} />;
}

export function Stat({ label, value, sub, tone = "ink", extra }: { label: string; value: React.ReactNode; sub?: string; tone?: "ink" | "live" | "sla" | "warn" | "brand"; extra?: React.ReactNode }) {
  const cls = {
    ink: "grad-text",
    live: "grad-text-lime",
    sla: "grad-text-rose",
    warn: "text-[#D9B36A]",
    brand: "grad-text",
  }[tone];
  return (
    <GlowCard className="group p-5">
      <div className="text-[10px] font-medium uppercase tracking-[.22em] text-dim">{label}</div>
      <div className={clsx("display num-hero mt-2 text-[2rem] font-semibold leading-tight", cls)}>{value}</div>
      {sub ? <div className="mt-1.5 text-[11px] text-dim">{sub}</div> : null}
      {extra ? <div className="mt-2.5">{extra}</div> : null}
    </GlowCard>
  );
}

export function Empty({ title, body }: { title: string; body: string }) {
  return (
    <div className="card p-14 text-center">
      <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-brand/20 to-fuchsia/10 text-xl shadow-glow">◈</div>
      <div className="display text-base font-semibold text-ink">{title}</div>
      <div className="mx-auto mt-2 max-w-sm text-[13px] leading-6 text-mute">{body}</div>
    </div>
  );
}

export function Toaster() {
  const { toasts, dismiss } = useUI();
  return (
    <div className="pointer-events-none fixed bottom-5 right-5 z-50 flex w-80 flex-col gap-2">
      <AnimatePresence>
        {toasts.map((t) => (
          <motion.button
            key={t.id}
            layout
            initial={{ opacity: 0, y: 12, filter: "blur(4px)" }}
            animate={{ opacity: 1, x: 0, scale: 1, filter: "blur(0px)" }}
            exit={{ opacity: 0, y: 6, filter: "blur(2px)" }}
            transition={{ type: "spring", stiffness: 380, damping: 28 }}
            onClick={() => dismiss(t.id)}
            className={clsx(
              "pointer-events-auto relative flex items-start gap-2.5 overflow-hidden rounded-xl border px-4 py-3 text-left text-[13px] font-medium backdrop-blur-xl",
              t.tone === "ok"
                ? "border-[#3ECFA5]/25 bg-[#3ECFA5]/[.08] text-[#7CD4B4]"
                : t.tone === "err"
                  ? "border-[#D98CA0]/25 bg-[#D98CA0]/[.08] text-[#D98CA0]"
                  : "border-[#B7AA87]/25 bg-[#B7AA87]/[.08] text-[#CDBF9D]"
            )}
          >
            <span className="mt-[1px] shrink-0">{t.tone === "ok" ? "✓" : t.tone === "err" ? "×" : "i"}</span>
            <span className="flex-1">{t.text}</span>
            <motion.span key={`${t.id}-bar`} initial={{ scaleX: 1 }} animate={{ scaleX: 0 }} transition={{ duration: 4.2, ease: "linear" }}
              className={clsx("absolute bottom-0 left-0 h-[2px] w-full origin-left", t.tone === "ok" ? "bg-[#7CD4B4]/50" : t.tone === "err" ? "bg-[#D98CA0]/50" : "bg-[#CDBF9D]/50")} />
          </motion.button>
        ))}
      </AnimatePresence>
    </div>
  );
}
