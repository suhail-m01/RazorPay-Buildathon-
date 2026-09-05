"use client";

import { motion, useReducedMotion } from "framer-motion";

const signals = [
  { label: "SIGNAL", detail: "payment risk", x: 18, y: 27 },
  { label: "DECISION", detail: "policy cleared", x: 76, y: 31 },
  { label: "RECOVERY", detail: "action ready", x: 71, y: 74 },
];

const particles = Array.from({ length: 18 }, (_, i) => ({
  left: `${14 + ((i * 41) % 72)}%`,
  top: `${12 + ((i * 59) % 74)}%`,
  size: i % 5 === 0 ? 2 : 1,
  delay: (i % 8) * 0.55,
  duration: 5.5 + (i % 5) * 0.8,
}));

export function AIRecoveryVisual({
  showValue = true,
  value = "₹2,84,500",
  compact = false,
}: {
  showValue?: boolean;
  value?: string;
  compact?: boolean;
}) {
  const reduce = useReducedMotion();

  return (
    <div className={`recover-visual ${compact ? "recover-visual-compact" : ""}`} aria-label="RecoverPay AI recovery engine visualization">
      <div className="recover-ambient" />
      <div className="recover-grid" />

      <div className="recover-particles" aria-hidden>
        {particles.map((p, i) => (
          <motion.i
            key={i}
            style={{ left: p.left, top: p.top, width: p.size, height: p.size }}
            animate={reduce ? undefined : { opacity: [0.08, 0.42, 0.08], y: [0, -8, 0] }}
            transition={reduce ? undefined : { duration: p.duration, delay: p.delay, repeat: Infinity, ease: "easeInOut" }}
          />
        ))}
      </div>

      <svg className="recover-arcs" viewBox="0 0 700 700" aria-hidden>
        <defs>
          <linearGradient id="recoverArcSoft" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#ffffff" stopOpacity="0" />
            <stop offset="48%" stopColor="#D6C8A5" stopOpacity="0.7" />
            <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
          </linearGradient>
        </defs>
        <circle cx="350" cy="350" r="218" fill="none" stroke="rgba(255,255,255,.055)" strokeWidth="1" />
        <circle cx="350" cy="350" r="184" fill="none" stroke="rgba(135,207,255,.075)" strokeWidth="1" strokeDasharray="1 16" />
        <motion.circle
          cx="350" cy="350" r="205" fill="none" stroke="url(#recoverArcSoft)" strokeWidth="1.5"
          strokeLinecap="round" strokeDasharray="72 1217"
          animate={reduce ? undefined : { rotate: 360 }}
          transition={reduce ? undefined : { duration: 18, repeat: Infinity, ease: "linear" }}
          style={{ transformOrigin: "350px 350px" }}
        />
        <motion.circle
          cx="350" cy="350" r="166" fill="none" stroke="rgba(255,255,255,.12)" strokeWidth="1"
          strokeDasharray="32 1010"
          animate={reduce ? undefined : { rotate: -360 }}
          transition={reduce ? undefined : { duration: 25, repeat: Infinity, ease: "linear" }}
          style={{ transformOrigin: "350px 350px" }}
        />
      </svg>

      <div className="recover-core">
        <motion.div
          className="recover-core-halo"
          animate={reduce ? undefined : { scale: [0.98, 1.035, 0.98], opacity: [0.38, 0.58, 0.38] }}
          transition={reduce ? undefined : { duration: 5.5, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.div
          className="recover-core-ring"
          animate={reduce ? undefined : { rotate: 360 }}
          transition={reduce ? undefined : { duration: 28, repeat: Infinity, ease: "linear" }}
        />
        <div className="recover-core-inner">
          <div className="recover-core-mark"><span /> RECOVERPAY AI</div>
          <div className="recover-core-label">{showValue ? "REVENUE AT RISK" : "AUTONOMOUS RECOVERY"}</div>
          {showValue ? <div className="recover-core-value">{value}</div> : <div className="recover-core-value recover-core-value-status">ACTIVE</div>}
          <div className="recover-core-status"><b /> MONITORING · POLICY-GATED</div>
        </div>
      </div>

      {!compact && signals.map((signal, i) => (
        <motion.div
          key={signal.label}
          className="recover-signal-card"
          style={{ left: `${signal.x}%`, top: `${signal.y}%` }}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35 + i * 0.1, duration: 0.55 }}
        >
          <span>{signal.label}</span>
          <strong>{signal.detail}</strong>
        </motion.div>
      ))}

      <div className="recover-bottom-readout">
        <span>DETECT</span><i /><span>DIAGNOSE</span><i /><b>DECIDE</b><i /><span>ACT</span><i /><span>RECOVER</span>
      </div>
    </div>
  );
}
