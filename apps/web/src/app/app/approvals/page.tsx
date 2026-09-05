"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, useApi, fmtINR, fmtDT } from "@/lib/api";
import { Badge, Empty, LivePill, Skeleton } from "@/components/ui";
import { FadeIn, PageTitle, Stagger, StaggerItem, motion, AnimatePresence } from "@/lib/motion";
import { useUI } from "@/lib/store";

type Approval = { id: string; case_id: string; case_seq: number; customer: string; amount_paise: number; is_demo_contact: boolean; suggested_action: string; reason: string; created_at: string };

export default function Approvals() {
  const router = useRouter();
  const push = useUI((s) => s.push);
  const { data, isLoading, refetch } = useApi<{ count: number; approvals: Approval[] }>(["approvals"], "/cases/approvals/list", { refetchInterval: 12_000 });
  const [reason, setReason] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState("");

  async function resolve(id: string, decision: "approved" | "rejected") {
    const why = reason[id]?.trim();
    if (decision === "rejected" && !why) { push("err", "Write a short reason for the rejection."); return; }
    setBusy(id);
    try {
      await api(`/cases/approvals/${id}`, { method: "POST", json: { decision, reason: why || "approved from console" } });
      push("ok", `Approval ${decision}`);
      refetch();
      router.refresh();
    } catch (e) { push("err", (e as Error).message); }
    setBusy("");
  }

  return (
    <div className="space-y-5">
      <PageTitle title="Human-in-the-loop approvals" sub="Disputes, exhausted ladders and high-risk suggestions route here — every decision is audited with your name and reason." />
      {isLoading ? (
        <div className="space-y-3">{[0, 1].map((i) => <Skeleton key={i} className="h-28" />)}</div>
      ) : !data || data.count === 0 ? (
        <Empty title="Inbox zero" body="Escalations from the agent (attempt caps, disputes, high-value actions) will appear here." />
      ) : (
        <motion.div layout className="space-y-3">
          <AnimatePresence initial={false}>
          {data.approvals.map((a) => (
            <motion.div layout key={a.id}
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.98, filter: "blur(3px)" }}
              transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}>
              <div className="card p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <a href={`/app/cases/${a.case_id}`} className="text-sm font-bold text-ink hover:text-brand2">Case #{a.case_seq} · {a.customer}</a>
                      <LivePill live={a.is_demo_contact} />
                      <Badge tone="warn">{fmtINR(a.amount_paise)}</Badge>
                    </div>
                    <div className="mt-1 text-[12px] text-mute">Suggested: <b className="text-ink">{a.suggested_action.replaceAll("_", " ")}</b> · {fmtDT(a.created_at)}</div>
                    <p className="mt-2 max-w-xl text-[13px] leading-6 text-mute">{a.reason}</p>
                  </div>
                  <div className="w-72 shrink-0 space-y-2">
                    <input className="input !py-2 !text-[12px]" placeholder="Reason (audited)" value={reason[a.id] ?? ""} onChange={(e) => setReason({ ...reason, [a.id]: e.target.value })} />
                    <div className="grid grid-cols-2 gap-2">
                      <button className="btn-primary !py-2 !text-[12px]" disabled={Boolean(busy)} onClick={() => resolve(a.id, "approved")}>{busy === a.id ? "Approving…" : "Approve & resume"}</button>
                      <button className="btn-danger !py-2 !text-[12px]" disabled={busy === a.id} onClick={() => resolve(a.id, "rejected")}>Reject & close</button>
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>
          ))}
          </AnimatePresence>
        </motion.div>
      )}
    </div>
  );
}
