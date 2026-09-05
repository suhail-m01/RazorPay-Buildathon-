"use client";

import Link from "next/link";
import { useState } from "react";
import { api, useApi, fmtINR, fmtDT, STAGE_LABEL, TYPE_LABEL, CAUSE_LABEL } from "@/lib/api";
import { Badge, Empty, Skeleton, riskTone, stageTone, statusTone } from "@/components/ui";
import { FadeIn, PageTitle, Stagger, StaggerItem } from "@/lib/motion";
import clsx from "clsx";

type CaseRow = { id: string; seq: number; customer: string; email: string; is_demo_contact: boolean; type: string; amount_paise: number; risk_score: number; root_cause: string | null; stage: string; status: string; attempts: number; promise_pending: boolean; updated_at: string; item: string };

const STATUSES = ["", "open", "recovered", "escalated", "stopped"];
const TYPES = ["", "payment_failed", "checkout_abandoned", "subscription_failed", "mandate_failed", "invoice_overdue"];

export default function CaseQueue() {
  const [status, setStatus] = useState("");
  const [type, setType] = useState("");
  const [q, setQ] = useState("");
  const [minRisk, setMinRisk] = useState(0);
  const { data, isLoading } = useApi<{ count: number; cases: CaseRow[] }>(
    ["cases", status, type, q, minRisk],
    `/cases?${new URLSearchParams({ ...(status && { status }), ...(type && { type }), ...(q && { q }), min_risk: String(minRisk) })}`,
    { refetchInterval: 15_000 }
  );

  return (
    <div className="space-y-5">
      <PageTitle title="Case queue" sub="Every recovery the agent is working — LIVE badges mark real, dispatch-safe contacts.">
        <div className="flex items-center gap-2 text-[12px] text-dim">
          <span>risk ≥</span>
          <input type="range" min={0} max={90} step={10} value={minRisk} onChange={(e) => setMinRisk(Number(e.target.value))} className="accent-brand" />
          <span className="w-6 font-bold text-ink">{minRisk}</span>
        </div>
      </PageTitle>

      <FadeIn className="flex flex-wrap items-center gap-2">
        {STATUSES.map((s) => (
          <button key={s || "all"} onClick={() => setStatus(s)}
            className={clsx("pill transition-all", status === s ? "pill-brand" : "pill-mute hover:text-ink")}>
            {s ? s.toUpperCase() : "ALL STATUS"}
          </button>
        ))}
        <span className="mx-1 h-4 w-px bg-line2" />
        {TYPES.map((t) => (
          <button key={t || "all"} onClick={() => setType(t)}
            className={clsx("pill transition-all", type === t ? "pill-cyan" : "pill-mute hover:text-ink")}>
            {t ? TYPE_LABEL[t] : "ALL TYPES"}
          </button>
        ))}
        <input className="input !w-52 !py-1.5 !text-[12px]" placeholder="search name/email/phone" value={q} onChange={(e) => setQ(e.target.value)} />
      </FadeIn>

      {isLoading ? (
        <div className="space-y-2">{[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-14" />)}</div>
      ) : !data || data.count === 0 ? (
        <Empty title="No cases match" body="Adjust the filters — or inject a test case from the dashboard." />
      ) : (
        <Stagger gap={0.035} className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[960px]">
              <thead className="border-b border-line"><tr>
                <th className="table-th">Case</th><th className="table-th">Customer</th><th className="table-th">For</th><th className="table-th">Type</th>
                <th className="table-th">Amount</th><th className="table-th">Risk</th><th className="table-th">AI diagnosis</th>
                <th className="table-th">Stage</th><th className="table-th">Status</th><th className="table-th">Updated</th>
              </tr></thead>
              <tbody>
                {data.cases.slice(0, 120).map((c) => (
                  <StaggerItem key={c.id} className="contents">
                    <tr className="group border-b border-line/50 transition-all last:border-0 hover:bg-white/[.03] hover:shadow-[inset_2px_0_0_0_#D6C8A5]">
                      <td className="table-td">
                        <Link href={`/app/cases/${c.id}`} className="display font-bold text-ink transition-all hover:text-brand2 group-hover:translate-x-0.5">#{c.seq}</Link>
                        {c.promise_pending ? <Badge tone="warn">hold</Badge> : null}
                      </td>
                      <td className="table-td">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{c.customer}</span>
                        </div>
                        <div className="text-[11px] text-dim">{c.email}</div>
                      </td>
                      <td className="table-td max-w-[180px] truncate text-[12px] text-mute" title={c.item}>{c.item}</td>
                      <td className="table-td text-[12px] text-mute">{TYPE_LABEL[c.type] ?? c.type}</td>
                      <td className="table-td font-semibold">{fmtINR(c.amount_paise)}</td>
                      <td className="table-td">
                      <span className="flex items-center gap-2">
                        <span className="h-[3px] w-10 overflow-hidden rounded-full bg-white/[.06]"><span className={`block h-full ${c.risk_score >= 70 ? "bg-[#D98CA0]" : c.risk_score >= 40 ? "bg-[#D9B36A]" : "bg-[#B7AA87]"}`} style={{ width: `${c.risk_score}%` }} /></span>
                        <span className="num-hero text-[12px] text-mute">{c.risk_score}</span>
                      </span>
                    </td>
                      <td className="table-td text-[12px]">{c.root_cause ? <span className="text-mute">{CAUSE_LABEL[c.root_cause] ?? c.root_cause}</span> : "—"}</td>
                      <td className="table-td"><Badge tone={stageTone(c.stage)}>{STAGE_LABEL[c.stage] ?? c.stage}</Badge></td>
                      <td className="table-td"><Badge tone={statusTone(c.status)}>{c.status}</Badge></td>
                      <td className="table-td text-[11px] text-dim">{fmtDT(c.updated_at)}</td>
                    </tr>
                  </StaggerItem>
                ))}
              </tbody>
            </table>
          </div>
        </Stagger>
      )}
    </div>
  );
}
