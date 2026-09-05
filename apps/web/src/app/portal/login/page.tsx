"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthShell, Err } from "@/components/AuthCard";
import { api, savePortalSession } from "@/lib/api";

export default function CustomerLogin() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  return (
    <AuthShell
      title="Customer portal"
      sub="See what you owe, why a payment failed, and pay in one tap."
      footer={<>Got a magic link? Just open it. · <Link className="text-brand2 hover:underline" href="/portal/register">Create an account</Link> · <Link className="text-mute hover:text-ink" href="/login">Merchant login</Link></>}
    >
      <form
        className="space-y-4"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true); setError("");
          try {
            const r = await api<{ portal_token: string }>("/portal/login", { method: "POST", json: { email, password } });
            savePortalSession(r.portal_token);
            router.push("/portal");
          } catch (err) {
            setError((err as Error).message);
            setBusy(false);
          }
        }}
      >
        <div><label className="label">Email</label><input className="input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" /></div>
        <div><label className="label">Password</label><input className="input" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} /></div>
        <Err msg={error} />
        <button className="btn-primary w-full !py-3" disabled={busy}>{busy ? "Signing in…" : "Log in"}</button>
      </form>
    </AuthShell>
  );
}
