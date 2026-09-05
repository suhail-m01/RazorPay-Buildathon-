"use client";

import { useState } from "react";
import { api, useApi, fmtDT } from "@/lib/api";
import { Badge, Skeleton } from "@/components/ui";
import { FadeIn, PageTitle, Stagger, StaggerItem } from "@/lib/motion";
import { useUI } from "@/lib/store";
import { SuccessCheck } from "@/components/motion";

type Log = { id: number; case_id: string | null; actor: string; action: string; reason_code: string | null; channel: string | null; message: string | null; simulated: boolean; created_at: string };

export default function Audit() {
  const push = useUI((s) => s.push);
  const [page, setPage] = useState(0);
  const { data, isLoading, refetch } = useApi<{ count: number; logs: Log[] }>(["audit", page], `/cases/audit/list?page=${page}&size=60`);
  const [chain, setChain] = useState<string>("");
  const [verifyState, setVerifyState] = useState<"idle" | "checking" | "verified" | "broken">("idle");

  return (
    <div className="space-y-5">
      <PageTitle title="Audit trail" sub="Append-only and hash-chained — any edit or deletion breaks verification.">
        <div className="flex gap-2">
          <button className="btn-ghost !py-2 !text-[12px]" onClick={async () => {
            setVerifyState("checking");
            try {
              const r = await api<{ ok: boolean; checked: number }>("/cases/audit/verify");
              setChain(r.ok ? `Chain intact — ${r.checked} entries verified` : "CHAIN BROKEN");
              setVerifyState(r.ok ? "verified" : "broken");
              push(r.ok ? "ok" : "err", r.ok ? `Chain intact (${r.checked} entries)` : "Chain verification FAILED");
            } catch (e) { push("err", (e as Error).message); setVerifyState("idle"); }
          }}>
            {verifyState === "checking" ? "Verifying…" : verifyState === "verified" ? "✓ Verified" : "Verify chain"}
          </button>
          <button className="btn-ghost !py-2 !text-[12px]" onClick={async () => {
            const r = await api<{ logs: Log[] }>("/cases/audit/list?page=0&size=2000");
            const rows = ["id,timestamp,actor,action,reason,channel,simulated,case_id"].concat(
              r.logs.map((l) => [l.id, l.created_at, l.actor, l.action, l.reason_code ?? "", l.channel ?? "", l.simulated, l.case_id ?? ""].join(",")));
            const blob = new Blob([rows.join("\n")], { type: "text/csv" });
            const a = document.createElement("a");
            a.href = URL.createObjectURL(blob);
            a.download = "recoverpay-compliance-report.csv";
            a.click();
            push("ok", "Compliance CSV exported (PII-free)");
            void refetch;
          }}>Export CSV</button>
        </div>
      </PageTitle>

      {chain ? (
  <FadeIn><div className={`flex items-center gap-2.5 rounded-xl border px-4 py-2.5 text-[13px] font-medium ${chain.startsWith("Chain intact") ? "border-lime/30 bg-lime/10 text-lime" : "border-rose/30 bg-rose/10 text-rose"}`}>
    {chain.startsWith("Chain intact") ? <SuccessCheck size={16} /> : <span className="text-base">⚠</span>}{chain}
  </div></FadeIn>
) : null}

      {isLoading || !data ? (
        <div className="space-y-2">{[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-12" />)}</div>
      ) : (
        <Stagger gap={0.03} className="card overflow-hidden">
          <div className="max-h-[70vh] overflow-auto">
            <table className="w-full min-w-[880px]">
              <thead className="sticky top-0 border-b border-line bg-card/95 backdrop-blur"><tr>
                <th className="table-th">#</th><th className="table-th">When</th><th className="table-th">Actor</th>
                <th className="table-th">Action</th><th className="table-th">Reason</th><th className="table-th">Channel</th>
                <th className="table-th">Mode</th><th className="table-th">Case</th>
              </tr></thead>
              <tbody>
                {data.logs.map((l) => (
                  <StaggerItem key={l.id} className="contents">
                    <tr className="border-b border-line/40 last:border-0 hover:bg-white/[.02]">
                      <td className="table-td font-mono text-[11px] text-dim">{l.id}</td>
                      <td className="table-td text-[11px] text-dim">{fmtDT(l.created_at)}</td>
                      <td className="table-td text-[12px]">{l.actor}</td>
                      <td className="table-td text-[12px] font-semibold">{l.action.replaceAll("_", " ")}</td>
                      <td className="table-td font-mono text-[11px] text-brand2">{l.reason_code ?? "—"}</td>
                      <td className="table-td text-[11px] uppercase text-dim">{l.channel ?? "—"}</td>
                      <td className="table-td"><Badge tone={l.simulated ? "mute" : "live"}>{l.simulated ? "sim" : "real"}</Badge></td>
                      <td className="table-td text-[11px]">{l.case_id ? <a className="text-brand2 hover:underline" href={`/app/cases/${l.case_id}`}>{l.case_id.slice(-6)}</a> : "—"}</td>
                    </tr>
                  </StaggerItem>
                ))}
              </tbody>
            </table>
          </div>
        </Stagger>
      )}
      <div className="flex items-center justify-between text-[12px] text-mute">
        <span>Page {page + 1}</span>
        <div className="flex gap-2">
          {page > 0 ? <button className="btn-ghost !py-1.5" onClick={() => setPage(page - 1)}>← Prev</button> : null}
          {data && data.logs.length === 60 ? <button className="btn-ghost !py-1.5" onClick={() => setPage(page + 1)}>Next →</button> : null}
        </div>
      </div>
    </div>
  );
}
