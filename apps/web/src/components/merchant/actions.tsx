"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { AIThinking } from "@/components/motion";
import { useUI } from "@/lib/store";

export function TickButton() {
  const push = useUI((s) => s.push);
  const [busy, setBusy] = useState(false);
  return (
    <button className="btn-ghost !py-2" disabled={busy} onClick={async () => {
      setBusy(true);
      try {
        const r = await api<{ summary: { promises_broken: number; advanced: number; escalated: number } }>("/admin/tick", { method: "POST", json: {} });
        push("info", `Tick: advanced ${r.summary.advanced}, lapsed ${r.summary.promises_broken}, escalated ${r.summary.escalated}`);
      } catch (e) { push("err", (e as Error).message); }
      setBusy(false);
    }}>{busy ? "Running…" : "Run tick"}</button>
  );
}

export function InjectButton() {
  const router = useRouter();
  const push = useUI((s) => s.push);
  const [busy, setBusy] = useState(false);
  return (
    <button className="btn-primary !py-2" disabled={busy} onClick={async () => {
      setBusy(true);
      try {
        const r = await api<{ seq: number; result: string }>("/cases/inject", { method: "POST", json: { case_type: "random" } });
        push("ok", `Case #${r.seq} injected → pipeline ran: ${r.result}`);
        router.refresh();
      } catch (e) { push("err", (e as Error).message); }
      setBusy(false);
    }}>{busy ? "Running pipeline…" : "Inject test case"}</button>
  );
}

export function CaseActions({ caseId, stage, status }: { caseId: string; stage: string; status: string }) {
  const router = useRouter();
  const push = useUI((s) => s.push);
  const [busy, setBusy] = useState("");
  const run = async (label: string, fn: () => Promise<unknown>) => {
    setBusy(label);
    try { await fn(); push("ok", `${label} done`); router.refresh(); } catch (e) { push("err", (e as Error).message); }
    setBusy("");
  };
  const done = status === "recovered" || status === "closed" || status === "stopped";
  return (
    <div className="space-y-2">
      <button className="btn-primary w-full" disabled={Boolean(busy) || done}
        onClick={() => run("Advance", () => api(`/cases/${caseId}/advance`, { method: "POST", json: {} }).then((r) => { push("info", `Ladder: ${(r as { status: string }).status}`); }))}>
        {busy === "Advance" ? "Running…" : done ? "Case closed" : "Advance ladder step"}
      </button>
      <button className="btn-ghost w-full !py-2" disabled={Boolean(busy)}
        onClick={() => run("Magic link", async () => {
          const r = await api<{ url: string }>(`/cases/${caseId}/magic-link`, { method: "POST", json: {} });
          try { await navigator.clipboard.writeText(r.url); push("ok", "Customer link copied"); } catch { push("info", r.url); }
        })}>
        Customer magic link
      </button>
      <button className="btn-ghost w-full !py-2" disabled={Boolean(busy)}
        onClick={() => run("Payment link", async () => {
          const r = await api<{ url: string }>(`/cases/${caseId}/payment-link`, { method: "POST", json: {} });
          try { await navigator.clipboard.writeText(r.url); push("ok", "Payment link copied"); } catch { push("info", r.url); }
        })}>
        Get payment link
      </button>
      <p className="text-[10px] leading-4 text-dim">Stage: {stage} · sends are policy-gated and simulated for synthetic contacts.</p>
    </div>
  );
}
