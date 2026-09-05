"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthShell, Err } from "@/components/AuthCard";
import { api, savePortalSession } from "@/lib/api";

export default function CustomerRegister() {
  const router = useRouter();
  const [f, setF] = useState({ name: "", email: "", password: "", phone: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });

  return (
    <AuthShell
      title="Create your portal account"
      sub="Use the email your reminders go to — your dues link up automatically."
      footer={<>Already registered? <Link className="text-brand2 hover:underline" href="/portal/login">Log in</Link></>}
    >
      <form
        className="space-y-4"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true); setError("");
          try {
            const r = await api<{ portal_token: string }>("/portal/register", { method: "POST", json: f });
            savePortalSession(r.portal_token);
            router.push("/portal");
          } catch (err) {
            setError((err as Error).message);
            setBusy(false);
          }
        }}
      >
        <div><label className="label">Full name</label><input className="input" required value={f.name} onChange={set("name")} /></div>
        <div><label className="label">Email</label><input className="input" type="email" required value={f.email} onChange={set("email")} /></div>
        <div className="grid grid-cols-2 gap-3">
          <div><label className="label">Phone</label><input className="input" required value={f.phone} onChange={set("phone")} placeholder="+91…" /></div>
          <div><label className="label">Password (min 8)</label><input className="input" type="password" required minLength={8} value={f.password} onChange={set("password")} /></div>
        </div>
        <Err msg={error} />
        <button className="btn-primary w-full !py-3" disabled={busy}>{busy ? "Creating…" : "Create account"}</button>
      </form>
    </AuthShell>
  );
}
