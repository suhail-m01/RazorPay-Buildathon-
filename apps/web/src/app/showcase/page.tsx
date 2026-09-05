"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Logo } from "@/components/ui";
import {
  GlowCard, SmartButton, SuccessCheck, CopyFeedback, AnimatedStatus,
  PulseDot, TimelineLine, TimelineNode, CountUp, Shake, EASE,
} from "@/components/motion";
import { Stagger, StaggerItem } from "@/lib/motion";

/** One page. Every animation. No login, no API — pure motion proof. */
export default function Showcase() {
  const [tick, setTick] = useState(0);
  const [status, setStatus] = useState("OPEN");
  const [err, setErr] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setTick((v) => v + 1), 3200);
    return () => clearInterval(t);
  }, []);

  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <div className="mb-2 flex items-center gap-3"><Logo size="lg" /><span className="pill pill-brand">motion showcase</span></div>
      <h1 className="display text-3xl font-extrabold">Every animation, <span className="shimmer-text">one page</span></h1>
      <p className="mb-10 text-[13px] text-mute">If nothing on this page moves, tell me — otherwise these exact effects are live across the app.</p>

      {/* 1 — counters + staggered entrance */}
      <Section n={1} title="Staggered entrance + counting numbers">
        <Stagger className="grid grid-cols-3 gap-4" gap={0.12} key={tick}>
          {["49536", "72.5", "57212"].map((v, i) => (
            <StaggerItem key={i}>
              <GlowCard className="p-5">
                <div className="text-[10px] uppercase tracking-widest text-dim">{["recovered ₹", "rate %", "direct ₹"][i]}</div>
                <div className="display mt-1 text-3xl font-bold grad-text">
                  <CountUp key={`${tick}-${i}`} value={Number(v)} format={(n) => n.toLocaleString("en-IN", { maximumFractionDigits: 1 })} />
                </div>
              </GlowCard>
            </StaggerItem>
          ))}
        </Stagger>
        <p className="mt-2 text-[11px] text-dim">re-staggers every few seconds — watch cards blur-in one by one, numbers spring up</p>
      </Section>

      {/* 2 — buttons with lifecycle */}
      <Section n={2} title="Buttons: idle → spinner → checkmark">
        <div className="flex flex-wrap items-center gap-3">
          <SmartButton tone="primary" onClick={() => new Promise((r) => setTimeout(r, 1200))}>Advance ladder step</SmartButton>
          <SmartButton tone="ghost" onClick={() => new Promise((r) => setTimeout(r, 900))}>Get payment link</SmartButton>
          <CopyFeedback onCopy={() => new Promise((r) => setTimeout(r, 300))} label="Copy link" />
        </div>
        <p className="mt-2 text-[11px] text-dim">click them — label crossfades → spinner → drawn checkmark ✓</p>
      </Section>

      {/* 3 — timeline */}
      <Section n={3} title="Investigation timeline (case detail)">
        <div className="card p-6">
          <div className="relative space-y-5">
            <TimelineLine />
            {[["Case detected", "live"], ["AI diagnosis · soft_decline 95%", "brand"], ["Policy decision · quiet-hours checked", "cyan"], ["WhatsApp sent", "warn"], ["Promise received · 3-day hold", "brand"]].map(([label, tone], i) => (
              <motion.div key={i} initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.15 + i * 0.14, duration: 0.4, ease: EASE }} className="relative pl-8">
                <TimelineNode delay={0.15 + i * 0.14} latest={i === 4} tone={tone as "live"} />
                <span className="text-[13px] font-semibold text-ink">{label}</span>
              </motion.div>
            ))}
          </div>
        </div>
        <p className="mt-2 text-[11px] text-dim">line grows downward · nodes pop sequentially · latest node pulses</p>
      </Section>

      {/* 4 — status morph + success check */}
      <Section n={4} title="Status transitions">
        <div className="flex flex-wrap items-center gap-4">
          <button className="btn-ghost !py-2" onClick={() => setStatus(status === "OPEN" ? "RECOVERED" : status === "RECOVERED" ? "ESCALATED" : "OPEN")}>
            cycle status →
          </button>
          <span className="pill pill-brand text-[12px]"><AnimatedStatus status={status} /></span>
          {status === "RECOVERED" ? <span className="pill pill-live"><SuccessCheck size={13} /> quiet celebration</span> : null}
        </div>
        <p className="mt-2 text-[11px] text-dim">badge crossfades through the cycle; recovered draws a checkmark</p>
      </Section>

      {/* 5 — glow cards / cursor */}
      <Section n={5} title="Cursor-glow cards (hover these)">
        <div className="grid grid-cols-2 gap-4">
          {["Hover me — light follows your cursor", "and me — violet glow tracks you"].map((t) => (
            <GlowCard key={t} className="p-6"><span className="text-[13px] text-mute">{t}</span></GlowCard>
          ))}
        </div>
      </Section>

      {/* 6 — error shake */}
      <Section n={6} title="Form error shake">
        <button className="btn-danger !py-2" onClick={() => setErr((v) => v + 1)}>trigger error</button>
        <div className="mt-3">
          <Shake trigger={err}>
            {err > 0 ? <div className="rounded-xl border border-rose/30 bg-rose/10 px-4 py-2.5 text-[13px] text-rose">Wrong email or password.</div> : <div className="text-[12px] text-dim">click the button</div>}
          </Shake>
        </div>
      </Section>

      {/* 7 — live dots + feed behaviour */}
      <Section n={7} title="Live indicators & feed items">
        <div className="flex flex-wrap items-center gap-5">
          <span className="pill pill-live"><PulseDot size={6} /> fast-sync 10s</span>
          <span className="pill pill-cyan"><PulseDot size={6} color="#A7B2AA" /> sse connected</span>
          <span className="pill pill-warn"><PulseDot size={6} color="#FBBF24" /> promise hold</span>
        </div>
        <div className="mt-4 space-y-1.5">
          <AnimatePresence initial={false}>
            {[0, 1, 2].map((i) => (
              <motion.div key={`${tick}-${i}`} layout initial={{ opacity: 0, y: -16, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0 }}
                transition={{ type: "spring", stiffness: 320, damping: 26 }}
                className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-[12px] ${i === 0 ? "border-brand2/50 bg-brand/10" : "border-line/50 bg-white/[.02]"}`}>
                <span className="grad-text">✦</span><span className="font-semibold text-ink/90">payment_captured</span>
                <span className="pill pill-live ml-auto">real</span>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
        <p className="mt-2 text-[11px] text-dim">new events slide in from the top with a highlight that settles — cycles every few seconds</p>
      </Section>

      {/* 8 — shimmer + ring */}
      <Section n={8} title="Ambient effects">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="card p-6"><div className="display text-2xl font-extrabold">Flowing <span className="shimmer-text">gradient</span> text</div></div>
          <div className="card ring-border p-6 flex items-center justify-center"><span className="text-[13px] text-mute">rotating conic border ring →</span></div>
        </div>
      </Section>

      <div className="mt-12 rounded-2xl border border-line2 bg-white/[.02] p-5 text-[13px] text-mute">
        <b className="text-ink">Where these live in the app:</b> #1 Dashboard KPIs · #2 every action button · #3 Case detail timeline · #4 case headers · #5 Dashboard cards · #6 login errors · #7 dashboard live wire · #8 landing + login.
        Route transitions (blur-slide) fire on every navigation. Sidebar active pill morphs as you switch pages.
      </div>
    </main>
  );
}

function Section({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <motion.section initial={{ opacity: 0, y: 18 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-40px" }} transition={{ duration: 0.5, ease: EASE }} className="mb-12">
      <h2 className="display mb-3 text-sm font-bold text-mute"><span className="grad-text mr-2">0{n}</span>{title}</h2>
      {children}
    </motion.section>
  );
}
