"use client";

import { useApi } from "@/lib/api";
import { Badge, Skeleton } from "@/components/ui";
import { FadeIn, PageTitle, Stagger, StaggerItem, motion } from "@/lib/motion";

type Pb = { key: string; name: string; version: number; status: string; traffic_share: number; definition: Record<string, unknown> };

export default function Playbooks() {
  const { data, isLoading } = useApi<{ playbooks: Pb[] }>(["playbooks"], "/admin/playbooks");
  return (
    <div className="space-y-5">
      <PageTitle title="Playbooks" sub="Versioned JSON policies the Decide engine runs. Traffic shares sum to 100% across active rows." />
      {isLoading || !data ? (
        <div className="grid gap-4 lg:grid-cols-2">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-56" />)}</div>
      ) : (
        <Stagger className="grid gap-4 lg:grid-cols-2">
          {data.playbooks.map((p) => (
            <StaggerItem key={p.key}>
              <div className="card h-full p-5">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-bold text-ink">{p.name}</div>
                    <div className="mt-0.5 font-mono text-[11px] text-dim">{p.key} · v{p.version}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge tone="live">{p.status}</Badge>
                    <Badge tone="brand">{p.traffic_share}%</Badge>
                  </div>
                </div>
                <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/5">
                  <div className="h-full rounded-full bg-gradient-to-r from-brand to-cyan" style={{ width: `${p.traffic_share}%` }} />
                </div>
                <pre className="mt-4 max-h-44 overflow-auto rounded-lg border border-white/[.05] bg-black/40 p-3 font-mono text-[11px] leading-5 text-[#CDBF9D]">{JSON.stringify(p.definition, null, 2)}</pre>
              </div>
            </StaggerItem>
          ))}
        </Stagger>
      )}
    </div>
  );
}
