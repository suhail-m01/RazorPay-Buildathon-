"use client";

import { motion, useReducedMotion } from "framer-motion";

const arcs = [0, 1, 2, 3, 4, 5];
const sparks = Array.from({ length: 24 }, (_, i) => i);
const satellites = [0, 1, 2, 3];

export function LandingRecoveryPreview() {
  const reduce = useReducedMotion();

  return (
    <div className="opening-visual" aria-hidden>
      <div className="opening-vignette" />
      <div className="opening-grid" />
      <div className="opening-aura opening-aura-a" />
      <div className="opening-aura opening-aura-b" />
      <motion.div
        className="opening-radiance"
        animate={reduce ? undefined : { opacity: [0.28, 0.62, 0.28], scale: [0.94, 1.06, 0.94] }}
        transition={reduce ? undefined : { duration: 6.8, repeat: Infinity, ease: "easeInOut" }}
      />

      <motion.div
        className="opening-core-wrap"
        animate={reduce ? undefined : { y: [0, -8, 0], scale: [1, 1.014, 1] }}
        transition={reduce ? undefined : { duration: 7, repeat: Infinity, ease: "easeInOut" }}
      >
        <motion.div
          className="opening-pulse-ring opening-pulse-ring-a"
          animate={reduce ? undefined : { scale: [0.9, 1.16, 0.9], opacity: [0, 0.34, 0] }}
          transition={reduce ? undefined : { duration: 5.4, repeat: Infinity, ease: "easeOut" }}
        />
        <motion.div
          className="opening-pulse-ring opening-pulse-ring-b"
          animate={reduce ? undefined : { scale: [0.88, 1.2, 0.88], opacity: [0, 0.22, 0] }}
          transition={reduce ? undefined : { duration: 5.4, delay: 2.7, repeat: Infinity, ease: "easeOut" }}
        />

        <div className="opening-core-halo" />
        <div className="opening-core">
          <motion.div
            className="opening-core-sheen"
            animate={reduce ? undefined : { x: ["-120%", "150%"] }}
            transition={reduce ? undefined : { duration: 5.8, repeat: Infinity, ease: "easeInOut", repeatDelay: 1.4 }}
          />
          <div className="opening-core-inner" />
          <div className="opening-core-line opening-core-line-a" />
          <div className="opening-core-line opening-core-line-b" />
          <div className="opening-core-line opening-core-line-c" />
        </div>

        {arcs.map((arc) => (
          <motion.div
            key={arc}
            className={`opening-arc opening-arc-${arc + 1}`}
            animate={reduce ? undefined : { rotate: arc % 2 === 0 ? 360 : -360 }}
            transition={reduce ? undefined : { duration: 16 + arc * 3, repeat: Infinity, ease: "linear" }}
          />
        ))}

        {satellites.map((satellite) => (
          <motion.div
            key={satellite}
            className={`opening-satellite-track opening-satellite-track-${satellite + 1}`}
            animate={reduce ? undefined : { rotate: satellite % 2 === 0 ? 360 : -360 }}
            transition={reduce ? undefined : { duration: 10 + satellite * 3.25, repeat: Infinity, ease: "linear" }}
          >
            <i />
          </motion.div>
        ))}
      </motion.div>

      <div className="opening-particles">
        {sparks.map((spark) => (
          <motion.i
            key={spark}
            className={`opening-particle opening-particle-${spark + 1}`}
            animate={reduce ? undefined : {
              opacity: [0.06, 0.72, 0.06],
              scale: [0.6, 1.45, 0.6],
              y: [0, spark % 2 === 0 ? -16 : 16, 0],
            }}
            transition={reduce ? undefined : {
              duration: 3.5 + (spark % 5) * 0.7,
              delay: (spark % 8) * 0.22,
              repeat: Infinity,
              ease: "easeInOut",
            }}
          />
        ))}
      </div>

      <motion.div
        className="opening-scan"
        animate={reduce ? undefined : { opacity: [0, 0.88, 0], scaleX: [0.28, 1, 0.28] }}
        transition={reduce ? undefined : { duration: 5.5, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="opening-scan opening-scan-secondary"
        animate={reduce ? undefined : { opacity: [0, 0.42, 0], scaleX: [0.18, 0.78, 0.18], y: [-72, 72, -72] }}
        transition={reduce ? undefined : { duration: 8.2, repeat: Infinity, ease: "easeInOut" }}
      />
    </div>
  );
}
