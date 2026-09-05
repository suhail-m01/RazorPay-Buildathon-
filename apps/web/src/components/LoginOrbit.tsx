"use client";

import { motion, useReducedMotion } from "framer-motion";

export function LoginOrbit() {
  const reduce = useReducedMotion();
  return (
    <div className="login-orbit" aria-hidden="true">
      <motion.div className="login-orbit-a" animate={reduce ? undefined : { rotate: 360 }} transition={reduce ? undefined : { duration: 28, repeat: Infinity, ease: "linear" }} />
      <motion.div className="login-orbit-b" animate={reduce ? undefined : { rotate: -360 }} transition={reduce ? undefined : { duration: 19, repeat: Infinity, ease: "linear" }} />
      <motion.div className="login-orbit-c" animate={reduce ? undefined : { rotate: 360 }} transition={reduce ? undefined : { duration: 42, repeat: Infinity, ease: "linear" }} />
      <motion.div className="login-core" animate={reduce ? undefined : { scale: [0.97, 1.03, 0.97] }} transition={reduce ? undefined : { duration: 4.8, repeat: Infinity, ease: "easeInOut" }}>
        <div className="login-core-inner">
          <span className="login-core-mark">RP</span>
          <span className="login-core-title">RECOVERY</span>
          <span className="login-core-sub">AI COMMAND</span>
        </div>
      </motion.div>
      <span className="login-signal login-signal-1">DETECT</span>
      <span className="login-signal login-signal-2">DECIDE</span>
      <span className="login-signal login-signal-3">RECOVER</span>
    </div>
  );
}
