"use client";

import { useState } from "react";
import Link from "next/link";
import { api, useApi, fmtINR } from "@/lib/api";
import { FadeIn, PageTitle, motion } from "@/lib/motion";
import { Badge, Skeleton } from "@/components/ui";

type Analytics={kpis:{at_risk_paise:number;recovered_paise:number;recovery_rate:number;open_cases:number;escalated_cases:number;stopped_cases:number};by_root_cause:Record<string,{cases:number;amount_paise:number}>};

const examples=["How much revenue did we recover?","What is revenue at risk?","Show recovery rate","What are the top causes?","How many high value cases do we have?"];

export default function AgentPage(){
 const {data,isLoading}=useApi<Analytics>(["agent-context"],"/analytics",{refetchInterval:20000});
 const [text,setText]=useState(""); const [busy,setBusy]=useState(false);
 const [messages,setMessages]=useState<{role:"user"|"agent";text:string;source?:string}[]>([]);
 async function ask(value=text){
   if(!value.trim())return; setBusy(true); setMessages(m=>[...m,{role:"user",text:value.trim()}]); setText("");
   try{const r=await api<{ok:boolean;message:string;source?:string}>("/agent/command",{method:"POST",json:{text:value}});setMessages(m=>[...m,{role:"agent",text:r.message,source:r.source}]);}
   catch(e){setMessages(m=>[...m,{role:"agent",text:(e as Error).message}]);} finally{setBusy(false);}
 }
 return <div className="space-y-6">
  <PageTitle title="RecoverPay agent" sub="A grounded operations interface. It answers from live application data and refuses unsupported commands rather than guessing.">
   <Link href="/app" className="btn-ghost !py-2">← Command centre</Link>
  </PageTitle>
  <FadeIn><div className="relative overflow-hidden rounded-[24px] border border-brand2/20 bg-gradient-to-br from-[#171923] to-[#0a0c11] p-6 shadow-lift">
    <div className="absolute -right-16 -top-16 h-48 w-48 rounded-full bg-brand/15 blur-3xl"/>
    <div className="relative grid gap-6 lg:grid-cols-[1fr_1.2fr]">
      <div><div className="pill pill-brand">BOUNDED AGENT</div><h2 className="display mt-4 text-3xl font-semibold text-ink">Ask about the money.<br/><span className="grad-text">Get a sourced answer.</span></h2><p className="mt-3 max-w-lg text-[13px] leading-6 text-mute">This layer is deliberately narrow: it reads RecoverPay's current case and analytics state. It cannot invent metrics or bypass policy-protected actions.</p>
      {data?<div className="mt-5 grid grid-cols-3 gap-2"><div className="rounded-xl border border-line/60 bg-white/[.03] p-3"><div className="text-[9px] uppercase tracking-wider text-dim">At risk</div><div className="mt-1 num-hero text-lg font-semibold text-sla">{fmtINR(data.kpis.at_risk_paise)}</div></div><div className="rounded-xl border border-line/60 bg-white/[.03] p-3"><div className="text-[9px] uppercase tracking-wider text-dim">Recovered</div><div className="mt-1 num-hero text-lg font-semibold text-live">{fmtINR(data.kpis.recovered_paise)}</div></div><div className="rounded-xl border border-line/60 bg-white/[.03] p-3"><div className="text-[9px] uppercase tracking-wider text-dim">Rate</div><div className="mt-1 num-hero text-lg font-semibold text-ink">{(data.kpis.recovery_rate*100).toFixed(1)}%</div></div></div>:<Skeleton className="mt-5 h-20"/>}</div>
      <div className="rounded-2xl border border-white/[.08] bg-black/20 p-4"><div className="mb-4 flex items-center justify-between"><span className="text-[10px] uppercase tracking-[.2em] text-dim">Operations console</span><Badge tone="live">grounded</Badge></div><div className="min-h-[190px] space-y-3">{messages.length===0?<div className="grid h-[190px] place-items-center text-center text-[12px] text-dim"><div><div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-2xl border border-brand2/20 bg-brand/10 text-brand2">◈</div>Choose a question below<br/>or ask your own.</div></div>:messages.slice(-5).map((m,i)=><motion.div key={i} initial={{opacity:0,y:8}} animate={{opacity:1,y:0}} className={m.role==="user"?"ml-10 rounded-xl border border-line/60 bg-white/[.04] p-3 text-[12px] text-ink":"mr-6 rounded-xl border border-brand2/15 bg-brand/5 p-3 text-[12px] leading-5 text-mute"}>{m.text}{m.source?<div className="mt-1 text-[9px] uppercase tracking-wider text-dim">source · {m.source}</div>:null}</motion.div>)}</div><div className="mt-3 flex gap-2"><input className="input" value={text} onChange={e=>setText(e.target.value)} onKeyDown={e=>{if(e.key==="Enter")void ask()}} placeholder="Ask RecoverPay…" disabled={busy}/><button className="btn-primary shrink-0" onClick={()=>void ask()} disabled={busy||!text.trim()}>{busy?"…":"Ask"}</button></div></div>
    </div>
  </div></FadeIn>
  <FadeIn delay={.08}><div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{examples.map(x=><button key={x} onClick={()=>void ask(x)} className="rounded-xl border border-line/60 bg-white/[.02] px-4 py-3 text-left text-[12px] text-mute transition hover:border-brand2/30 hover:bg-brand/5 hover:text-ink">{x}<span className="float-right text-brand2">→</span></button>)}</div></FadeIn>
  <FadeIn delay={.12}><div className="card p-5"><div className="flex items-center justify-between"><div><h2 className="text-sm font-bold text-ink">Agent boundaries</h2><p className="text-[11px] text-dim">Why this is safer than an unrestricted AI operator</p></div><Badge tone="warn">policy-owned actions</Badge></div><div className="mt-4 grid gap-3 md:grid-cols-4">{[["AI","diagnose · classify · recommend"],["Policy","consent · quiet hours · caps"],["System","payments · webhooks · audit"],["Human","approve · override · escalate"]].map(([a,b])=><div key={a} className="rounded-xl border border-line/60 bg-white/[.02] p-3"><div className="text-[10px] font-semibold uppercase tracking-wider text-brand2">{a}</div><div className="mt-1 text-[11px] text-mute">{b}</div></div>)}</div></div></FadeIn>
 </div>
}
