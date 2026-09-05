"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthShell, Err } from "@/components/AuthCard";
import { api, saveMerchantSession } from "@/lib/api";

export default function MerchantRegister() {
  const router = useRouter();
  const [f, setF] = useState({ name: "", email: "", password: "", company: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });

  return (
    <AuthShell
      title="Create your console"
      sub="Registering with an existing company name joins that team."
      footer={<>Already registered? <Link className="text-brand2 hover:underline" href="/login">Log in</Link></>}
    >
      <form
        className="space-y-4"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true); setError("");
          try {
            const r = await api<{ token: string; refresh?: string }>("/auth/register", { method: "POST", json: f });
            saveMerchantSession(r.token, r.refresh);
            router.push("/app");
          } catch (err) {
            setError((err as Error).message);
            setBusy(false);
          }
        }}
      >
        <div><label className="label">Full name</label><input className="input" required value={f.name} onChange={set("name")} placeholder="Anjali Mehra" /></div>
        <div><label className="label">Work email</label><input className="input" type="email" required value={f.email} onChange={set("email")} placeholder="you@company.in" /></div>
        <div><label className="label">Company</label><input className="input" required value={f.company} onChange={set("company")} placeholder="Kirana Cloud Technologies" /></div>
        <div><label className="label">Password (min 8)</label><input className="input" type="password" required minLength={8} value={f.password} onChange={set("password")} /></div>
        <Err msg={error} />
        <button className="btn-primary w-full !py-3" disabled={busy}>{busy ? "Creating…" : "Create account"}</button>
      </form>
    </AuthShell>
  );
}
