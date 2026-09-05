"use client";

/**
 * RecoverPay global motion system — reusable primitives.
 * Rules: springs for interaction, ease-out entrances, transform/opacity only.
 * All primitives respect prefers-reduced-motion via framer-motion defaults + CSS.
 */
import { AnimatePresence, motion, useInView, useMotionValue, useSpring, useReducedMotion } from "framer-motion";
import { useEffect, useRef, useState, type ReactNode } from "react";
import clsx from "clsx";

export const EASE = [0.22, 1, 0.36, 1] as const;
export const springSoft = { type: "spring", stiffness: 260, damping: 26 } as const;
export const springSnappy = { type: "spring", stiffness: 420, damping: 30 } as const;

/* ---------------- entrances ---------------- */

export function Reveal({ children, delay = 0, y = 14, className = "", once = true }: { children: ReactNode; delay?: number; y?: number; className?: string; once?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once, margin: "-30px" });
  return (
    <motion.div ref={ref} className={className}
      initial={{ opacity: 0, y, filter: "blur(3px)" }}
      animate={inView ? { opacity: 1, y: 0, filter: "blur(0px)" } : {}}
      transition={{ duration: 0.5, delay, ease: EASE }}>
      {children}
    </motion.div>
  );
}

export function ScaleIn({ children, delay = 0, className = "" }: { children: ReactNode; delay?: number; className?: string }) {
  return (
    <motion.div className={className}
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4, delay, ease: EASE }}>
      {children}
    </motion.div>
  );
}

/* ---------------- containers ---------------- */

export function Stagger({ children, className = "", gap = 0.06, delay = 0 }: { children: ReactNode; className?: string; gap?: number; delay?: number }) {
  return (
    <motion.div className={className}
      initial="hidden" animate="show"
      variants={{ hidden: {}, show: { transition: { staggerChildren: gap, delayChildren: delay } } }}>
      {children}
    </motion.div>
  );
}

export function StaggerItem({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <motion.div className={className}
      variants={{ hidden: { opacity: 0, y: 16, filter: "blur(3px)" }, show: { opacity: 1, y: 0, filter: "blur(0px)", transition: { duration: 0.5, ease: EASE } } }}>
      {children}
    </motion.div>
  );
}

export function FadeIn({ children, delay = 0, y = 14, className = "" }: { children: ReactNode; delay?: number; y?: number; className?: string }) {
  return (
    <motion.div className={className}
      initial={{ opacity: 0, y }} animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.55, delay, ease: EASE }}>
      {children}
    </motion.div>
  );
}

export function PageTitle({ title, sub, children }: { title: string; sub?: string; children?: ReactNode }) {
  return (
    <FadeIn className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="display text-2xl font-bold tracking-tight text-ink">{title}</h1>
        {sub ? <p className="mt-1 text-[13px] text-mute">{sub}</p> : null}
      </div>
      {children}
    </FadeIn>
  );
}

/* ---------------- numbers ---------------- */

export function CountUp({ value, format, className = "" }: { value: number; format?: (n: number) => string; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-30px" });
  const reduce = useReducedMotion();
  const mv = useMotionValue(0);
  const spring = useSpring(mv, { stiffness: 80, damping: 22 });
  const [display, setDisplay] = useState("0");
  const [prev, setPrev] = useState(0);

  useEffect(() => {
    if (reduce) { setDisplay((format ?? String)(value)); return; }
    if (inView || value !== prev) { mv.set(value); setPrev(value); }
  }, [inView, value, mv, prev, reduce, format]);

  useEffect(() => spring.on("change", (v) => setDisplay((format ?? ((n: number) => String(Math.round(n))))(v))), [spring, format]);

  return <span ref={ref} className={className}>{display}</span>;
}

/** Animated number transition for value changes (e.g. risk 32 → 48). */
export function AnimatedNumber({ value, format }: { value: number; format?: (n: number) => string }) {
  const spring = useSpring(value, { stiffness: 90, damping: 20 });
  const [d, setD] = useState(value);
  useEffect(() => { spring.set(value); }, [value, spring]);
  useEffect(() => spring.on("change", (v) => setD(v)), [spring]);
  return <>{(format ?? String)(Math.round(d))}</>;
}

/* ---------------- interactive primitives ---------------- */

/** Card with cursor-following radial highlight + lift. */
export function GlowCard({ children, className = "", glow = "rgba(141,134,201,0.10)" }: { children: ReactNode; className?: string; glow?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ x: -300, y: -300 });
  const [hover, setHover] = useState(false);
  return (
    <motion.div
      ref={ref}
      className={clsx("card card-lift card-edge relative overflow-hidden", className)}
      onPointerMove={(e) => { const r = ref.current!.getBoundingClientRect(); setPos({ x: e.clientX - r.left, y: e.clientY - r.top }); }}
      onPointerEnter={() => setHover(true)}
      onPointerLeave={() => setHover(false)}
      whileHover={{ y: -3 }}
      transition={springSoft}
    >
      <motion.div aria-hidden className="pointer-events-none absolute inset-0"
        animate={{ opacity: hover ? 1 : 0, background: `radial-gradient(320px circle at ${pos.x}px ${pos.y}px, ${glow}, transparent 65%)` }}
        transition={{ duration: 0.25 }} />
      {children}
    </motion.div>
  );
}

/** Button with idle → processing → success lifecycle. */
export function SmartButton({
  children, onClick, className = "", tone = "primary", successMs = 1400,
}: {
  children: ReactNode;
  onClick?: () => Promise<unknown> | void;
  className?: string;
  tone?: "primary" | "ghost" | "danger";
  successMs?: number;
}) {
  const [state, setState] = useState<"idle" | "busy" | "done">("idle");
  const toneCls = tone === "primary" ? "btn-primary" : tone === "danger" ? "btn-danger" : "btn-ghost";

  async function run() {
    if (state !== "idle" || !onClick) return;
    setState("busy");
    try {
      await onClick();
      setState("done");
      setTimeout(() => setState("idle"), successMs);
    } catch {
      setState("idle");
    }
  }

  return (
    <motion.button whileTap={{ scale: 0.97 }} onClick={run} className={clsx(toneCls, className)} disabled={state !== "idle"}>
      <AnimatePresence mode="wait" initial={false}>
        {state === "idle" && (
          <motion.span key="idle" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.15 }}>
            {children}
          </motion.span>
        )}
        {state === "busy" && (
          <motion.span key="busy" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex items-center gap-2">
            <motion.span className="h-3.5 w-3.5 rounded-full border-2 border-white/30 border-t-white" animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 0.7, ease: "linear" }} />
            Working…
          </motion.span>
        )}
        {state === "done" && (
          <motion.span key="done" initial={{ opacity: 0, scale: 0.7 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }} className="flex items-center gap-2">
            <SuccessCheck size={14} /> Done
          </motion.span>
        )}
      </AnimatePresence>
    </motion.button>
  );
}

/** SVG checkmark draw animation. */
export function SuccessCheck({ size = 18, className = "" }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className}>
      <motion.circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.35, ease: EASE }} />
      <motion.path d="M7 12.5l3.2 3.2L17 9" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.35, delay: 0.2, ease: EASE }} />
    </svg>
  );
}

/** Copy → Copied ✓ feedback button content. */
export function CopyFeedback({ onCopy, label = "Copy", className = "" }: { onCopy: () => Promise<void> | void; label?: string; className?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button className={clsx("btn-ghost !py-1.5 !text-[12px]", className)}
      onClick={async () => { await onCopy(); setCopied(true); setTimeout(() => setCopied(false), 1500); }}>
      <AnimatePresence mode="wait" initial={false}>
        {copied ? (
          <motion.span key="y" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} className="flex items-center gap-1.5 text-lime">
            <SuccessCheck size={12} /> Copied
          </motion.span>
        ) : (
          <motion.span key="n" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}>
            {label}
          </motion.span>
        )}
      </AnimatePresence>
    </button>
  );
}

/** Status badge that crossfades when the status changes. */
export function AnimatedStatus({ status, className }: { status: string; className?: string }) {
  return (
    <span className={clsx("relative inline-flex", className)}>
      <AnimatePresence mode="wait" initial={false}>
        <motion.span key={status} initial={{ opacity: 0, y: 5, scale: 0.94 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -5, scale: 0.94 }} transition={{ duration: 0.2 }}>
          {status}
        </motion.span>
      </AnimatePresence>
    </span>
  );
}

/** Subtle expanding pulse ring for live dots. */
export function PulseDot({ color = "#A3E635", size = 6 }: { color?: string; size?: number }) {
  return (
    <span className="relative inline-flex" style={{ width: size, height: size }}>
      <motion.span className="absolute inset-0 rounded-full" style={{ background: color }}
        animate={{ scale: [1, 2, 1], opacity: [0.5, 0, 0.5] }} transition={{ duration: 2.2, repeat: Infinity, ease: "easeOut" }} />
      <span className="relative rounded-full" style={{ width: size, height: size, background: color, boxShadow: `0 0 10px 1px ${color}` }} />
    </span>
  );
}

/** Timeline: growing connecting line. */
export function TimelineLine({ active = true }: { active?: boolean }) {
  return (
    <motion.div aria-hidden className="absolute left-[9px] top-5 bottom-2 w-px origin-top bg-gradient-to-b from-brand2/70 via-line2 to-transparent"
      initial={{ scaleY: 0 }} animate={{ scaleY: 1 }} transition={{ duration: 0.8, ease: EASE }} />
  );
}

/** Timeline node that pops in. */
export function TimelineNode({ delay = 0, latest = false, tone = "brand" }: { delay?: number; latest?: boolean; tone?: "brand" | "live" | "warn" | "sla" | "cyan" }) {
  const bg = { brand: "#CDBF9D", live: "#7CD4B4", warn: "#D9B36A", sla: "#D98CA0", cyan: "#8FC3D6" }[tone];
  return (
    <motion.span aria-hidden className="absolute left-0 top-1 flex h-[19px] w-[19px] items-center justify-center"
      initial={{ scale: 0, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ delay, ...springSnappy }}>
      {latest && <motion.span className="absolute inset-0 rounded-full" style={{ background: bg }} animate={{ scale: [1, 1.9], opacity: [0.5, 0] }} transition={{ duration: 1.8, repeat: Infinity }} />}
      <span className="relative h-[9px] w-[9px] rounded-full" style={{ background: bg, boxShadow: latest ? `0 0 12px 1px ${bg}` : `0 0 5px ${bg}40` }} />
    </motion.span>
  );
}

/** Form error with subtle shake (0→-4→4→-2→2→0). */
export function Shake({ children, trigger }: { children: ReactNode; trigger: unknown }) {
  return (
    <motion.div key={String(trigger)} initial={false} animate={trigger ? { x: [0, -4, 4, -2, 2, 0] } : {}} transition={{ duration: 0.35 }}>
      {children}
    </motion.div>
  );
}

export { AnimatePresence, motion };


/** Contextual AI processing state — rotating micro-status over a radial signal. */
export function AIThinking({ label = "ANALYSING", lines = ["Payment history", "Failure patterns", "Policy window", "Previous attempts"] }: { label?: string; lines?: string[] }) {
  const [i, setI] = useState(0);
  useEffect(() => { const t = setInterval(() => setI((v) => (v + 1) % lines.length), 1400); return () => clearInterval(t); }, [lines.length]);
  return (
    <div className="flex items-center gap-3">
      <span className="relative flex h-5 w-5 items-center justify-center">
        <motion.span className="absolute inset-0 rounded-full border border-brand2/40 border-t-brand2" animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1.6, ease: "linear" }} />
        <motion.span className="h-1 w-1 rounded-full bg-brand2" animate={{ opacity: [0.4, 1, 0.4] }} transition={{ repeat: Infinity, duration: 1.6 }} />
      </span>
      <span className="flex flex-col leading-tight">
        <span className="text-[10px] font-semibold uppercase tracking-[.2em] text-dim">{label}</span>
        <AnimatePresence mode="wait">
          <motion.span key={i} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }} transition={{ duration: 0.25 }}
            className="text-[12px] text-mute">{lines[i]}</motion.span>
        </AnimatePresence>
      </span>
    </div>
  );
}

/** Radial risk meter — animates to score once. */
export function RiskRing({ score, size = 40 }: { score: number; size?: number }) {
  const r = (size - 5) / 2;
  const c = 2 * Math.PI * r;
  const color = score >= 70 ? "#D98CA0" : score >= 40 ? "#D9B36A" : "#B7AA87";
  return (
    <span className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} stroke="rgba(255,255,255,.07)" strokeWidth="2.5" fill="none" />
        <motion.circle cx={size / 2} cy={size / 2} r={r} stroke={color} strokeWidth="2.5" fill="none" strokeLinecap="round"
          strokeDasharray={c} initial={{ strokeDashoffset: c }} whileInView={{ strokeDashoffset: c * (1 - score / 100) }}
          viewport={{ once: true }} transition={{ duration: 0.9, ease: EASE }} />
      </svg>
      <span className="num-hero absolute text-[11px] font-semibold" style={{ color }}>{score}</span>
    </span>
  );
}

/** Real-data sparkline (values: number[]) with draw-on reveal. */
export function Sparkline({ values, width = 92, height = 24, tone = "#B7AA87" }: { values: number[]; width?: number; height?: number; tone?: string }) {
  if (!values || values.length < 2) return <span style={{ width, height }} />;
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * width},${height - ((v - min) / (max - min || 1)) * (height - 3) - 1.5}`);
  const d = `M ${pts.join(" L ")}`;
  return (
    <svg width={width} height={height} className="overflow-visible">
      <motion.path d={d} fill="none" stroke={tone} strokeWidth="1.5" strokeLinecap="round" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.9, ease: EASE }} />
      <circle cx={pts[pts.length - 1].split(",")[0]} cy={pts[pts.length - 1].split(",")[1]} r="1.8" fill={tone} />
    </svg>
  );
}
