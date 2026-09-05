"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthShell, Err } from "@/components/AuthCard";
import { Shake } from "@/components/motion";
import { api, saveMerchantSession } from "@/lib/api";
import { LoginOrbit } from "@/components/LoginOrbit";

export default function MerchantLogin() {
  const router = useRouter();
  const [email, setEmail] = useState("anjali@kirana.cloud");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  return (
    <AuthShell
      title="Merchant console"
      sub="Revenue-ops login for your recovery team."
      footer={<>New here? <Link className="text-brand2 hover:underline" href="/register">Create an account</Link> · <Link className="text-mute hover:text-ink" href="/portal/login">Customer login</Link></>}
    >
      <div className="mb-6 rounded-2xl border border-white/[.07] bg-white/[.018] px-3 py-2 overflow-hidden">
        <LoginOrbit />
      </div>
      <form
        className="space-y-4"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true); setError("");
          try {
            const r = await api<{ token: string; refresh?: string }>("/auth/login", { method: "POST", json: { email, password } });
            saveMerchantSession(r.token, r.refresh);
            router.push("/app");
          } catch (err) {
            setError((err as Error).message);
            setBusy(false);
          }
        }}
      >
        <div>
          <label className="label">Work email</label>
          <input className="input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.in" />
        </div>
        <div>
          <label className="label">Password</label>
          <input className="input" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
        </div>
        <Shake trigger={error}><Err msg={error} /></Shake>
        <button className="btn-primary w-full !py-3" disabled={busy}>{busy ? "Signing in…" : "Log in"}</button>
        <p className="text-center text-[11px] leading-5 text-dim">Demo: anjali@kirana.cloud · Punah@123</p>
      </form>
    </AuthShell>
  );
}
