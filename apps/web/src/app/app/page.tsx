"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, useApi, fmtINR } from "@/lib/api";
import { CountUp, FadeIn, PageTitle, Stagger, StaggerItem, motion } from "@/lib/motion";
import { AIThinking, PulseDot, Sparkline } from "@/components/motion";
import { Badge, Skeleton, Stat } from "@/components/ui";
import { WeeklyChart } from "@/components/merchant/Charts";
import { RecoveryPipeline } from "@/components/RecoveryPipeline";
import { ExecutiveRecoveryPanel } from "@/components/ExecutiveRecoveryPanel";
import { TickButton } from "@/components/merchant/actions";
import { AnimatePresence } from "framer-motion";

type Kpis = {
  at_risk_paise:number; open_cases:number; recovered_cases:number; recovered_paise:number;
  recovery_rate:number; uplift_vs_naive_pct_points:number; cost_to_recover_paise:number;
  customers_contacted:number; stopped_cases:number; escalated_cases:number; avg_recovery_hours:number;
  request_payments?:number; pending_requests?:number;
};
type Analytics = {
  kpis:Kpis;
  demo?:{cases:number;recovered_cases:number;recovered_paise:number;at_risk_paise:number};
  by_product?:{product:string;cases:number;at_risk_paise:number;recovered_paise:number;demo?:boolean}[];
  by_root_cause:Record<string,{cases:number;recovered:number;amount_paise?:number}>;
  by_channel:Record<string,{cases:number;recovered:number}>;
  stage_counts:Record<string,number>;
  stage_value:Record<string,number>;
  promises:Record<string,number>;
  weekly:{label:string;agent_paise:number;baseline_paise:number}[];
};
type Feed={action:string;case_id:string;actor:string;simulated:boolean;stamp:number};

const icon:Record<string,string>={payment_captured:"₹",send_email:"✉",send_whatsapp:"◌",send_sms:"⌁",diagnose:"◈",customer_reply:"↩",mark_promise_to_pay:"◷",case_detected:"●",escalate_to_human:"↗"};

export default function Dashboard(){
  const {data,isLoading}=useApi<Analytics>(["analytics"],"/analytics",{refetchInterval:15000});
  const [feed,setFeed]=useState<Feed[]>([]);
  useEffect(()=>{
    const es=new EventSource("/api/v1/events/stream");
    es.addEventListener("audit",e=>{
      try{
        const j=JSON.parse((e as MessageEvent).data);
        setFeed(v=>[{action:j.action,case_id:j.case_id,actor:j.actor,simulated:j.simulated,stamp:Date.now()+Math.random()},...v].slice(0,12));
      }catch{}
    });
    return()=>es.close();
  },[]);
  const k=data?.kpis;
  const total=Object.values(data?.by_root_cause||{}).reduce((n,v)=>n+v.cases,0);
  const stages: {key:string;label:string;value:number|undefined;state:"done"|"idle"|"active"}[]=data?[
    {key:"detect",label:"Detect",value:data.kpis.at_risk_paise,state:total?"done":"idle"},
    {key:"diagnose",label:"Diagnose",value:Object.values(data.by_root_cause||{}).reduce((n,v)=>n+v.amount_paise!,0)||undefined,state:total?"done":"idle"},
    {key:"decide",label:"Decide",value:undefined,state:total?"done":"idle"},
    {key:"act",label:"Act",value:undefined,state:k?.open_cases?"active":"done"},
    {key:"recover",label:"Recover",value:k?.recovered_paise,state:k?.recovered_cases?"done":"idle"},
  ]:[];

  return <div className="space-y-6">
    <PageTitle title="Revenue recovery command centre" sub="One operating view from revenue at risk to money recovered. The agent acts inside deterministic guardrails.">
      <div className="flex gap-2"><Link href="/app/agent" className="btn-ghost !py-2">Ask RecoverPay</Link><Link href="/app/payments" className="btn-primary !py-2">⚡ New request</Link><TickButton/></div>
    </PageTitle>

    {k ? <FadeIn><div className="relative overflow-hidden rounded-[22px] border border-[#D8C9A3]/20 bg-gradient-to-br from-[#171923] via-[#0e1017] to-[#0a0c11] p-6 shadow-lift">
      <div className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full bg-[#b7aa87]/10 blur-3xl"/>
      <div className="relative grid gap-7 lg:grid-cols-[1.1fr_1fr] lg:items-center">
        <div>
          <div className="flex items-center gap-2"><span className="pill pill-live"><PulseDot size={5}/> agent operating</span><span className="text-[10px] uppercase tracking-[.18em] text-dim">real activity only</span></div>
          <div className="mt-4 text-[10px] font-semibold uppercase tracking-[.22em] text-dim">Revenue at risk</div>
          <div className="mt-1 flex flex-wrap items-end gap-4"><div className="num-hero text-5xl font-semibold tracking-tight text-ink md:text-6xl"><CountUp value={k.at_risk_paise/100} format={n=>fmtINR(n*100)}/></div><span className="mb-2 text-[12px] text-mute">{k.open_cases} open recoveries</span></div>
          <div className="mt-4 max-w-xl text-[13px] leading-6 text-mute">RecoverPay detects leakage, diagnoses the failure, checks permission, executes the next bounded action and records the outcome.</div>
          <div className="mt-5 flex flex-wrap gap-2"><Link href="/app/cases" className="btn-primary !py-2">Open recovery queue →</Link><Link href="/app/batch" className="btn-ghost !py-2">Measure a batch</Link></div>
        </div>
        <div className="relative min-h-[390px] overflow-hidden rounded-2xl border border-white/[.07] bg-black/20">
          <div className="pointer-events-none absolute left-4 top-4 z-10 flex items-center gap-2"><span className="pill pill-brand">LIVE AGENT MAP</span><span className="text-[9px] uppercase tracking-[.18em] text-dim">private workspace</span></div>
          <ExecutiveRecoveryPanel value={fmtINR(k.at_risk_paise)} />
        </div>
      </div>
    </div></FadeIn>:null}

    {data?<FadeIn delay={.06}><RecoveryPipeline stages={stages}/></FadeIn>:null}

    <FadeIn delay={.08}>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[
          ["01", "SIGNAL INTAKE", "Payment events entering the engine", "live"],
          ["02", "AI DIAGNOSIS", "Evidence-backed cause classification", "ai"],
          ["03", "POLICY GATE", "Consent, timing, cost and caps", "policy"],
          ["04", "CHANNEL EXECUTION", "Email · WhatsApp · Voice", "act"],
        ].map(([n, title, text, tone], i) => <motion.div key={n} className="ai-signal-card" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: .1 + i * .06, duration: .45 }}>
          <div className="flex items-center justify-between"><span className="font-mono text-[9px] tracking-[.18em] text-dim">{n}</span><span className={`ai-signal-dot ${tone}`} /></div>
          <div className="mt-3 text-[11px] font-semibold tracking-[.12em] text-ink">{title}</div>
          <div className="mt-1 text-[10px] leading-4 text-dim">{text}</div>
          <div className="ai-signal-track"><motion.span initial={{ x: "-110%" }} animate={{ x: "210%" }} transition={{ duration: 2.8 + i * .3, repeat: Infinity, ease: "linear", delay: i * .25 }} /></div>
        </motion.div>)}
      </div>
    </FadeIn>

    {isLoading||!k?<div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{[1,2,3,4].map(i=><Skeleton key={i} className="h-28"/>)}</div>:
      <Stagger className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" delay={.1}><StaggerItem><Stat label="Revenue recovered" tone="live" value={<CountUp value={k.recovered_paise/100} format={n=>fmtINR(n*100)}/>} sub={`${k.recovered_cases} cases · avg ${k.avg_recovery_hours||0}h`} extra={<Sparkline values={data!.weekly.map(w=>w.agent_paise)} tone="#7CD4B4"/>}/></StaggerItem>
      <StaggerItem><Stat label="Customers contacted" value={k.customers_contacted} sub={`${k.open_cases} active · ${k.escalated_cases} escalated`}/></StaggerItem>
      <StaggerItem><Stat label="Stopped safely" tone="sla" value={k.stopped_cases} sub="opt-out / stopping rules"/></StaggerItem>
      <StaggerItem><Stat label="Recovery cost" tone="warn" value={fmtINR(k.cost_to_recover_paise,true)} sub={`${(k.cost_to_recover_paise/Math.max(1,k.recovered_paise)*100).toFixed(2)}% of recovered`}/></StaggerItem></Stagger>}

    <div className="grid gap-5 lg:grid-cols-3">
      <FadeIn delay={.12} className="lg:col-span-2"><div className="card p-5"><div className="mb-1 flex items-center justify-between"><div><h2 className="display text-sm font-bold text-ink">Agent vs naive recovery</h2><p className="text-[11px] text-dim">recovered ₹ per week · baseline is a documented assumption</p></div><Link href="/app/analytics" className="text-[11px] text-brand2 hover:text-ink">View analytics →</Link></div>{data?<WeeklyChart data={data.weekly}/>:<Skeleton className="h-64"/>}</div></FadeIn>
      <FadeIn delay={.16}><div className="card h-full p-5"><div className="mb-4 flex items-center justify-between"><div><div className="text-[10px] uppercase tracking-[.2em] text-dim">Agent state</div><h2 className="mt-1 text-sm font-bold text-ink">Working memory, not chain-of-thought</h2></div><Badge tone="live">bounded</Badge></div><AIThinking label="PROCESSING" lines={["payment failure context","recovery eligibility","policy guardrails","customer response"]}/><div className="mt-5 space-y-2 text-[12px]">{["AI diagnosis","Policy evaluation","Action execution","Outcome tracking"].map((x,i)=><div key={x} className="flex items-center gap-2 rounded-lg border border-line/50 bg-white/[.02] px-3 py-2"><span className="flex h-5 w-5 items-center justify-center rounded-full bg-live/10 text-[10px] text-live">✓</span><span className="text-mute">{x}</span><span className="ml-auto text-[10px] text-dim">{i<3?"guarded":"audit"}</span></div>)}</div></div></FadeIn>
    </div>

    <FadeIn delay={.2}><div className="card overflow-hidden"><div className="flex items-center justify-between border-b border-line/60 px-5 py-4"><div><h2 className="display text-sm font-bold text-ink">Live recovery feed</h2><p className="text-[11px] text-dim">SSE events from the real audit stream · no synthetic ticker</p></div><span className="pill pill-live"><PulseDot size={5}/> live</span></div><div className="divide-y divide-line/40">{feed.length? <AnimatePresence initial={false}>{feed.slice(0,7).map((f,i)=><motion.div key={f.stamp} layout initial={{opacity:0,y:-10}} animate={{opacity:1,y:0}} className="flex items-center gap-3 px-5 py-3"><span className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand/10 text-brand2">{icon[f.action]||"•"}</span><div className="min-w-0"><div className="text-[12px] font-semibold text-ink">{f.action.replaceAll("_"," ")}</div><div className="text-[10px] text-dim">{f.actor} · {f.case_id?.slice(-8)||"ledger"}</div></div><span className={`pill ml-auto ${f.simulated?"pill-mute":"pill-live"}`}>{f.simulated?"simulated":"real"}</span></motion.div>)}</AnimatePresence>:<div className="px-5 py-10 text-center text-[12px] text-dim">Waiting for the next agent or payment event.</div>}</div></div></FadeIn>

    {data?<FadeIn delay={.24}><div className="grid gap-5 lg:grid-cols-2"><div className="card p-5"><div className="mb-4 flex items-center justify-between"><div><h2 className="display text-sm font-bold text-ink">Revenue leakage by cause</h2><p className="text-[11px] text-dim">case count, real cohort</p></div><Link href="/app/cases" className="text-[11px] text-brand2">Investigate →</Link></div><div className="space-y-3">{Object.entries(data.by_root_cause).sort((a,b)=>b[1].cases-a[1].cases).slice(0,6).map(([cause,v])=><div key={cause}><div className="mb-1 flex justify-between text-[12px]"><span className="text-mute">{cause.replaceAll("_"," ")}</span><span className="font-semibold text-ink">{v.cases}</span></div><div className="h-1.5 rounded-full bg-white/[.06]"><motion.div className="h-full rounded-full bg-brand2/70" initial={{width:0}} animate={{width:`${(v.cases/Math.max(1,total))*100}%`}} transition={{duration:.7}}/></div></div>)}</div></div>
    <div className="card p-5"><div className="mb-4 flex items-center justify-between"><div><h2 className="display text-sm font-bold text-ink">Recovery controls</h2><p className="text-[11px] text-dim">visible stopping and escalation outcomes</p></div><Link href="/app/audit" className="text-[11px] text-brand2">Decision trace →</Link></div><div className="grid grid-cols-2 gap-3"><div className="rounded-xl border border-live/15 bg-live/5 p-4"><div className="text-[10px] uppercase tracking-wider text-dim">Promises kept</div><div className="mt-1 num-hero text-2xl font-semibold text-live">{data.promises.kept||0}</div></div><div className="rounded-xl border border-warn/15 bg-warn/5 p-4"><div className="text-[10px] uppercase tracking-wider text-dim">Pending promises</div><div className="mt-1 num-hero text-2xl font-semibold text-warn">{data.promises.pending||0}</div></div><div className="rounded-xl border border-sla/15 bg-sla/5 p-4"><div className="text-[10px] uppercase tracking-wider text-dim">Escalated</div><div className="mt-1 num-hero text-2xl font-semibold text-sla">{k?.escalated_cases||0}</div></div><div className="rounded-xl border border-line/60 bg-white/[.02] p-4"><div className="text-[10px] uppercase tracking-wider text-dim">Stopped</div><div className="mt-1 num-hero text-2xl font-semibold text-ink">{k?.stopped_cases||0}</div></div></div></div></div></FadeIn>:null}
  </div>
}
