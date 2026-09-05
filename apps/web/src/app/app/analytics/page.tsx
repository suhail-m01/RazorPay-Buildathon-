"use client";

import Link from "next/link";
import { useApi, fmtINR } from "@/lib/api";
import { FadeIn, PageTitle, Stagger, StaggerItem, motion } from "@/lib/motion";
import { Badge, Skeleton, Stat } from "@/components/ui";
import { WeeklyChart } from "@/components/merchant/Charts";

type Data={kpis:{at_risk_paise:number;recovered_paise:number;recovery_rate:number;avg_recovery_hours:number;customers_contacted:number;stopped_cases:number;escalated_cases:number;cost_to_recover_paise:number};by_root_cause:Record<string,{cases:number;recovered:number;amount_paise:number}>;by_channel:Record<string,{cases:number;recovered:number}>;by_type:Record<string,{cases:number;recovered:number;at_risk_paise:number;recovered_paise:number}>;stage_counts:Record<string,number>;stage_value:Record<string,number>;weekly:{label:string;agent_paise:number;baseline_paise:number}[]};

const label=(s:string)=>s.replaceAll("_"," ").replace(/\b\w/g,c=>c.toUpperCase());

export default function Analytics(){
 const {data,isLoading}=useApi<Data>(["analytics-detail"],"/analytics",{refetchInterval:20000});
 if(isLoading||!data)return <div className="space-y-4"><Skeleton className="h-28"/><Skeleton className="h-80"/><Skeleton className="h-64"/></div>;
 const k=data.kpis;
 const maxCause=Math.max(1,...Object.values(data.by_root_cause).map(x=>x.amount_paise));
 return <div className="space-y-6">
  <PageTitle title="Recovery analytics" sub="Outcome intelligence from the same case, payment and audit sources used by the agent.">
   <Link href="/app/batch" className="btn-primary !py-2">Run measured batch →</Link>
  </PageTitle>
  <Stagger className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><StaggerItem><Stat label="Revenue at risk" tone="sla" value={fmtINR(k.at_risk_paise)} sub="open recovery exposure"/></StaggerItem><StaggerItem><Stat label="Revenue recovered" tone="live" value={fmtINR(k.recovered_paise)} sub={`${(k.recovery_rate*100).toFixed(1)}% case recovery rate`}/></StaggerItem><StaggerItem><Stat label="Average recovery time" value={`${k.avg_recovery_hours||0}h`} sub={`${k.customers_contacted} customers contacted`}/></StaggerItem><StaggerItem><Stat label="Intervention cost" tone="warn" value={fmtINR(k.cost_to_recover_paise,true)} sub={`${k.escalated_cases} escalated · ${k.stopped_cases} stopped`}/></StaggerItem></Stagger>
  <FadeIn><div className="card p-5"><div className="mb-4 flex items-center justify-between"><div><h2 className="display text-sm font-bold text-ink">Revenue recovery trend</h2><p className="text-[11px] text-dim">agent outcome vs documented naive baseline</p></div><Badge tone="brand">real cohort</Badge></div><WeeklyChart data={data.weekly}/></div></FadeIn>
  <div className="grid gap-5 lg:grid-cols-2">
   <FadeIn><div className="card p-5"><h2 className="display text-sm font-bold text-ink">Revenue leakage by cause</h2><p className="mb-4 text-[11px] text-dim">amount at risk/recovered from actual cases</p><div className="space-y-4">{Object.entries(data.by_root_cause).sort((a,b)=>b[1].amount_paise-a[1].amount_paise).map(([cause,v])=><div key={cause}><div className="mb-1 flex justify-between text-[12px]"><span className="text-mute">{label(cause)}</span><span className="font-semibold text-ink">{fmtINR(v.amount_paise)}</span></div><div className="h-2 overflow-hidden rounded-full bg-white/[.05]"><motion.div className="h-full rounded-full bg-gradient-to-r from-[#b7aa87] to-[#7cd4b4]" initial={{width:0}} animate={{width:`${v.amount_paise/maxCause*100}%`}} transition={{duration:.7}}/></div><div className="mt-1 text-[10px] text-dim">{v.recovered} of {v.cases} recovered</div></div>)}</div></div></FadeIn>
   <FadeIn delay={.08}><div className="card p-5"><h2 className="display text-sm font-bold text-ink">Intervention performance</h2><p className="mb-4 text-[11px] text-dim">recovered cases by actual recorded channel</p><div className="space-y-3">{Object.entries(data.by_channel).sort((a,b)=>b[1].recovered-a[1].recovered).map(([ch,v])=><div key={ch} className="flex items-center gap-3"><span className="w-24 text-[12px] capitalize text-mute">{ch}</span><div className="h-2 flex-1 overflow-hidden rounded-full bg-white/[.05]"><motion.div className="h-full rounded-full bg-brand2/80" initial={{width:0}} animate={{width:`${v.cases? v.recovered/v.cases*100:0}%`}} transition={{duration:.7}}/></div><span className="w-16 text-right text-[11px] text-ink">{v.recovered}/{v.cases}</span></div>)}</div></div></FadeIn>
  </div>
  <div className="grid gap-5 lg:grid-cols-2">
   <FadeIn><div className="card p-5"><h2 className="display text-sm font-bold text-ink">Revenue source mix</h2><div className="mt-4 grid gap-2 sm:grid-cols-2">{Object.entries(data.by_type).map(([type,v])=><div key={type} className="rounded-xl border border-line/60 bg-white/[.02] p-3"><div className="text-[11px] uppercase tracking-wider text-dim">{label(type)}</div><div className="mt-1 num-hero text-lg font-semibold text-ink">{fmtINR(v.recovered_paise)}</div><div className="text-[10px] text-mute">{fmtINR(v.at_risk_paise)} still at risk · {v.cases} cases</div></div>)}</div></div></FadeIn>
   <FadeIn delay={.08}><div className="card p-5"><h2 className="display text-sm font-bold text-ink">Lifecycle distribution</h2><div className="mt-4 grid grid-cols-2 gap-2">{Object.entries(data.stage_counts).sort((a,b)=>b[1]-a[1]).map(([stage,n])=><div key={stage} className="flex items-center justify-between rounded-xl border border-line/60 bg-white/[.02] px-3 py-2"><span className="text-[11px] text-mute">{label(stage)}</span><span className="num-hero text-sm font-semibold text-ink">{n}</span></div>)}</div></div></FadeIn>
  </div>
  <FadeIn><div className="card border-warn/20 bg-warn/[.03] p-4 text-[11px] leading-5 text-mute"><b className="text-ink">Metric integrity:</b> headline analytics exclude @example.test batch/demo cohorts. Estimated baseline is explicitly labeled; it is not presented as a measured competitor result.</div></FadeIn>
 </div>
}
