"use client";

import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fmtINR } from "@/lib/api";

const tooltipStyle = { background: "#101218", border: "1px solid #2A2F42", borderRadius: 12, fontSize: 12, color: "#EDEFF7" };

export function WeeklyChart({ data }: { data: { label: string; agent_paise: number; baseline_paise: number }[] }) {
  const rows = data.map((d) => ({ ...d, agent: d.agent_paise / 100, baseline: d.baseline_paise / 100 }));
  return (
    <ResponsiveContainer width="100%" height={260}>
      <AreaChart data={rows} margin={{ top: 4, right: 4, left: 4, bottom: 0 }}>
        <defs>
          <linearGradient id="ag" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#A99B79" stopOpacity={0.5} />
            <stop offset="100%" stopColor="#A99B79" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="#1E2230" strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="label" stroke="#5D6478" fontSize={11} tickLine={false} axisLine={false} />
        <YAxis stroke="#5D6478" fontSize={11} tickLine={false} axisLine={false} tickFormatter={(v) => `₹${v >= 1000 ? `${Math.round(v / 1000)}k` : v}`} />
        <Tooltip contentStyle={tooltipStyle} formatter={(v: number, name) => [fmtINR(v * 100), name === "agent" ? "RecoverPay agent" : "Naive retry"]} />
        <Area type="monotone" dataKey="baseline" stroke="#5D6478" strokeDasharray="4 4" fill="transparent" strokeWidth={1.5} />
        <Area type="monotone" dataKey="agent" stroke="#C8B98F" fill="url(#ag)" strokeWidth={2.5} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function CauseBar({ data }: { data: { cause: string; recovered: number; open: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 4, right: 4, left: 4, bottom: 0 }}>
        <CartesianGrid stroke="#1E2230" strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="cause" stroke="#5D6478" fontSize={10} tickLine={false} axisLine={false} />
        <YAxis stroke="#5D6478" fontSize={11} tickLine={false} axisLine={false} />
        <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "rgba(255,255,255,.03)" }} />
        <Bar dataKey="recovered" stackId="a" fill="#A3E635" radius={[0, 0, 0, 0]} name="recovered" />
        <Bar dataKey="open" stackId="a" fill="#A99B79" radius={[6, 6, 0, 0]} name="open" />
      </BarChart>
    </ResponsiveContainer>
  );
}
