"use client";

import { motion, useReducedMotion } from "framer-motion";

export function ExecutiveRecoveryPanel({ value = "₹0" }: { value?: string }) {
  const reduce = useReducedMotion();
  const rows = [
    ["01", "Signal integrity", "Razorpay events", "LIVE"],
    ["02", "Decision layer", "Consent · timing · economics", "GUARDED"],
    ["03", "Action channel", "Email · WhatsApp · Voice", "ADAPTIVE"],
  ];
  return (
    <div className="executive-panel">
      <div className="executive-sheen" />
      <div className="executive-head">
        <div><span>AUTONOMOUS RECOVERY</span><strong>Decision intelligence</strong></div>
        <div className="executive-live"><i /> LIVE</div>
      </div>
      <div className="executive-value"><span>REVENUE CURRENTLY AT RISK</span><strong>{value}</strong><em>real-time exposure</em></div>
      <div className="executive-rule" />
      <div className="executive-rows">
        {rows.map(([n,t,d,s],i)=>(
          <motion.div key={n} className="executive-row" initial={{opacity:0,y:6}} animate={{opacity:1,y:0}} transition={{delay:.1+i*.07}}>
            <span>{n}</span><div><strong>{t}</strong><small>{d}</small></div><b>{s}</b>
          </motion.div>
        ))}
      </div>
      <div className="executive-flow"><span>DETECT</span><i/><span>DIAGNOSE</span><i/><b>DECIDE</b><i/><span>ACT</span><i/><span>RECOVER</span></div>
      <motion.div className="executive-scan" animate={reduce ? undefined : {x:["-120%","420%"]}} transition={reduce ? undefined : {duration:5.5,repeat:Infinity,ease:"easeInOut",repeatDelay:1.2}} />
    </div>
  );
}
