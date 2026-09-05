"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui";
import { FadeIn, PageTitle } from "@/lib/motion";
import { useUI } from "@/lib/store";

type Status = {
  razorpay: { ready: boolean; key_id: string; webhook_secret_set: boolean };
  email: { ready: boolean; mode: string; from: string; smtp_host: string; smtp_user: string };
  ai: { ready: boolean; provider: string };
  whatsapp: { ready: boolean; provider?: string; sid: string; from: string; content_sid?: string };
  vonage: { ready: boolean; application_id: string; from: string };
  voice: { ready: boolean; provider?: string; from: string; to: string };
};

const EMPTY = { vonage_application_id: "", vonage_private_key_path: "./private.key", vonage_whatsapp_from: "", vonage_whatsapp_to: "", vonage_voice_from: "", vonage_voice_to: "", rzp_key_id: "", rzp_key_secret: "", rzp_webhook_secret: "", resend_api_key: "", smtp_host: "", smtp_port: "587", smtp_user: "", smtp_pass: "", email_from: "", gemini_api_key: "", twilio_sid: "", twilio_token: "", twilio_whatsapp_from: "whatsapp:+17372508034", twilio_whatsapp_content_sid: "HX1e5ab5f00277942d4d4200328b4d403c", twilio_whatsapp_content_variables_json: "", twilio_voice_from: "+17372508034", twilio_voice_to: "+919380962272" };

export default function SettingsPage() {
  const push = useUI((s) => s.push);
  const [status, setStatus] = useState<Status | null>(null);
  const [f, setF] = useState({ ...EMPTY });
  const [testTo, setTestTo] = useState("");
  const [busy, setBusy] = useState("");

  function validateTwilioSid(value: string) {
    return !value || /^AC[a-fA-F0-9]{32}$/.test(value.trim());
  }

  const load = () => api<Status>("/setup").then(setStatus).catch((e) => push("err", e.message));
  useEffect(() => { void load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });

  async function save() {
    if (f.twilio_sid && !validateTwilioSid(f.twilio_sid)) {
      push("err", "Twilio Account SID must start with AC and contain 34 characters. Copy the Account SID from Twilio Home.");
      return;
    }
    setBusy("save");
    try {
      const clean = Object.fromEntries(Object.entries(f).filter(([, v]) => v !== ""));
      const r = await api<{ ok: boolean; message?: string; razorpay_ready: boolean; email_ready: boolean; whatsapp_ready?: boolean; voice_ready?: boolean }>("/setup", { method: "PUT", json: clean });
      if (!r.ok) { push("err", r.message ?? "Settings were not saved"); setBusy(""); return; }
      push("ok", `Saved — Razorpay ${r.razorpay_ready ? "ready" : "not set"}, email ${r.email_ready ? "ready" : "not set"}, WhatsApp ${r.whatsapp_ready ? "ready" : "not set"}, Voice ${r.voice_ready ? "ready" : "not set"}`);
      setF({ ...EMPTY });
      void load();
    } catch (e) { push("err", (e as Error).message); }
    setBusy("");
  }

  return (
    <div className="space-y-5">
      <PageTitle title="Settings" sub="Connect your own accounts — every order, payment link and email runs through them." />

      <FadeIn>
        <div className="card s4 p-5">
          <div className="flex flex-wrap items-center gap-3">
            <Badge tone={status?.razorpay.ready ? "live" : "warn"}><span className={`flow-node ${status?.razorpay.ready ? "done" : ""}`} style={{width:5,height:5,boxShadow:"none"}} /> RAZORPAY · {status?.razorpay.ready ? status.razorpay.key_id : "not connected"}</Badge>
            <Badge tone={status?.email.ready ? "live" : "warn"}>{status?.email.ready ? `EMAIL · ${status.email.mode}${status.email.from ? ` · ${status.email.from}` : ""}` : "EMAIL · not connected"}</Badge>
            <Badge tone={status?.ai.ready ? "live" : "warn"}><span className={`flow-node ${status?.ai.ready ? "done" : ""}`} style={{width:5,height:5,boxShadow:"none"}} /> AI · {status?.ai.ready ? status.ai.provider : "rules-only"}</Badge>
            <Badge tone={status?.whatsapp.ready ? "live" : "warn"}><span className={`flow-node ${status?.whatsapp.ready ? "done" : ""}`} style={{width:5,height:5,boxShadow:"none"}} /> WHATSAPP · {status?.whatsapp.ready ? (status.whatsapp.provider ?? "connected") : "not connected"}</Badge>
          </div>
          <p className="mt-3 text-[12px] leading-5 text-mute">
            Without keys the app still works end-to-end using the built-in test checkout — but connecting your real Razorpay test
            account makes every payment, decline and capture an actual Razorpay event. Test keys look like <span className="font-mono text-ink">rzp_test_…</span>.
          </p>
        </div>
      </FadeIn>

      <div className="grid gap-5 lg:grid-cols-2">
        <FadeIn delay={0.06}>
          <div className="card h-full space-y-3 p-5">
            <h2 className="text-sm font-bold text-ink">Razorpay (test mode)</h2>
            <div><label className="label">Key ID</label><input className="input font-mono !text-[12px]" value={f.rzp_key_id} onChange={set("rzp_key_id")} placeholder="rzp_test_xxxxxxxx" /></div>
            <div><label className="label">Key secret</label><input className="input font-mono !text-[12px]" type="password" value={f.rzp_key_secret} onChange={set("rzp_key_secret")} placeholder="••••••••" /></div>
            <div><label className="label">Webhook secret (optional — for hosted webhooks)</label><input className="input font-mono !text-[12px]" type="password" value={f.rzp_webhook_secret} onChange={set("rzp_webhook_secret")} placeholder="whsec_…" /></div>
            <button className="btn-ghost !py-2 !text-[12px]" disabled={busy === "rzp"}
              onClick={async () => { setBusy("rzp"); try { const r = await api<{ ok: boolean; message: string }>("/setup/test-razorpay", { method: "POST", json: {} }); push(r.ok ? "ok" : "err", r.message); } catch (e) { push("err", (e as Error).message); } setBusy(""); }}>
              {busy === "rzp" ? "Testing…" : "Test connection"}
            </button>
          </div>
        </FadeIn>

        <FadeIn delay={0.1}>
          <div className="card h-full space-y-3 p-5">
            <h2 className="text-sm font-bold text-ink">Email — Resend or SMTP</h2>
            <div><label className="label">Resend API key (or use SMTP below)</label><input className="input font-mono !text-[12px]" type="password" value={f.resend_api_key} onChange={set("resend_api_key")} placeholder="re_…" /></div>
            <div className="grid grid-cols-3 gap-2">
              <div className="col-span-2"><label className="label">SMTP host</label><input className="input !text-[12px]" value={f.smtp_host} onChange={set("smtp_host")} placeholder="smtp.gmail.com" /></div>
              <div><label className="label">Port</label><input className="input !text-[12px]" value={f.smtp_port} onChange={set("smtp_port")} /></div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div><label className="label">SMTP user</label><input className="input !text-[12px]" value={f.smtp_user} onChange={set("smtp_user")} placeholder="you@gmail.com" /></div>
              <div><label className="label">Password / app password</label><input className="input !text-[12px]" type="password" value={f.smtp_pass} onChange={set("smtp_pass")} /></div>
            </div>
            <div><label className="label">From address</label><input className="input !text-[12px]" value={f.email_from} onChange={set("email_from")} placeholder="You <you@gmail.com>" /></div>
            <div className="flex gap-2">
              <input className="input !py-2 !text-[12px]" value={testTo} onChange={(e) => setTestTo(e.target.value)} placeholder="send test email to…" />
              <button className="btn-ghost !py-2 !text-[12px] whitespace-nowrap" disabled={busy === "email" || !testTo}
                onClick={async () => { setBusy("email"); try { const r = await api<{ ok: boolean; message: string }>("/setup/test-email", { method: "POST", json: { to: testTo } }); push(r.ok ? "ok" : "err", r.message); } catch (e) { push("err", (e as Error).message); } setBusy(""); }}>
                {busy === "email" ? "Sending…" : "Send test"}
              </button>
            </div>
            <p className="text-[11px] leading-4 text-dim">Gmail: enable 2-step verification, create an App Password (myaccount.google.com/apppasswords), use it here — not your login password.</p>
          </div>
        </FadeIn>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <FadeIn delay={0.12}>
          <div className="card h-full space-y-3 p-5">
            <h2 className="text-sm font-bold text-ink">AI — Gemini (free tier)</h2>
            <p className="text-[12px] leading-5 text-mute">Powers root-cause diagnosis and reply parsing with real LLM output (strict JSON). Without a key the agent runs on deterministic rules — still compliant, less "AI" on stage.</p>
            <div><label className="label">Gemini API key</label><input className="input font-mono !text-[12px]" type="password" value={f.gemini_api_key} onChange={set("gemini_api_key")} placeholder="AIza…" /></div>
            <div className="flex items-center gap-2">
              <button className="btn-ghost !py-2 !text-[12px]" disabled={busy === "llm"}
                onClick={async () => { setBusy("llm"); try { const r = await api<{ ok: boolean; message: string }>("/setup/test-llm", { method: "POST", json: {} }); push(r.ok ? "ok" : "err", r.message); } catch (e) { push("err", (e as Error).message); } setBusy(""); }}>
                {busy === "llm" ? "Testing…" : "Test AI diagnosis"}
              </button>
              <a href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer" className="text-[11px] text-brand2 hover:underline">free key ↗</a>
            </div>
          </div>
        </FadeIn>

        <FadeIn delay={0.14}>
          <div className="card h-full space-y-3 p-5">
            <div className="flex items-center justify-between gap-3">
              <div><h2 className="text-sm font-bold text-ink">WhatsApp — Vonage Sandbox</h2><p className="mt-1 text-[11px] text-dim">Primary WhatsApp route for the buildathon demo. Uses the Vonage Messages API Sandbox and a local private key.</p></div>
              <Badge tone={status?.vonage?.ready ? "live" : "warn"}>{status?.vonage?.ready ? "VONAGE · READY" : "VONAGE · not connected"}</Badge>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div><label className="label">Application ID</label><input className="input font-mono !text-[12px]" autoComplete="off" value={f.vonage_application_id} onChange={set("vonage_application_id")} placeholder="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee" /></div>
              <div><label className="label">Private key path</label><input className="input font-mono !text-[12px]" value={f.vonage_private_key_path} onChange={set("vonage_private_key_path")} placeholder="./private.key" /></div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div><label className="label">Sandbox WhatsApp From</label><input className="input font-mono !text-[12px]" value={f.vonage_whatsapp_from} onChange={set("vonage_whatsapp_from")} placeholder="whatsapp:+..." /></div>
              <div><label className="label">Test To</label><input className="input font-mono !text-[12px]" value={f.vonage_whatsapp_to} onChange={set("vonage_whatsapp_to")} placeholder="+919..." /></div>
            </div>
            <div className="rounded-xl border border-white/[.07] bg-white/[.02] p-3 text-[11px] leading-5 text-mute">
              <b className="text-ink">Sandbox setup:</b> the recipient must be allow-listed in Vonage. Keep <span className="font-mono text-ink">private.key</span> inside <span className="font-mono text-ink">apps/api</span>. Never paste the private key into the dashboard or chat. Webhooks are configured against your current ngrok HTTPS URL.
            </div>
            <div className="flex gap-2">
              <button className="btn-ghost !py-2 !text-[12px] whitespace-nowrap" disabled={busy === "vonage" || !f.vonage_whatsapp_to} onClick={async () => { setBusy("vonage"); try { const r = await api<{ ok: boolean; message: string }>("/setup/test-vonage-whatsapp", { method: "POST", json: { to: f.vonage_whatsapp_to } }); push(r.ok ? "ok" : "err", r.message); } catch (e) { push("err", (e as Error).message); } setBusy(""); }}>
                {busy === "vonage" ? "Sending…" : "Send Vonage test"}
              </button>
            </div>
          </div>
        </FadeIn>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <FadeIn delay={0.16}>
          <div className="card h-full space-y-3 p-5">
            <div className="flex items-center justify-between gap-3">
              <div><h2 className="text-sm font-bold text-ink">Phone — Vonage Voice</h2><p className="mt-1 text-[11px] text-dim">Real outbound recovery calls use the same Vonage application and remain policy-gated. Twilio stays available as fallback.</p></div>
              <Badge tone={status?.voice?.ready ? "live" : "warn"}>{status?.voice?.ready ? "VOICE · READY" : "VOICE · not connected"}</Badge>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div><label className="label">Vonage Voice From</label><input className="input font-mono !text-[12px]" value={f.vonage_voice_from} onChange={set("vonage_voice_from")} placeholder="+44... / your Vonage virtual number" /></div>
              <div><label className="label">Test To</label><input className="input font-mono !text-[12px]" value={f.vonage_voice_to} onChange={set("vonage_voice_to")} placeholder="+919..." /></div>
            </div>
            <div className="rounded-xl border border-white/[.07] bg-white/[.02] p-3 text-[11px] leading-5 text-mute">
              <b className="text-ink">Vonage Voice:</b> use a Voice-capable Vonage virtual number linked to this application. The WhatsApp Sandbox sender is not automatically a callable Voice number. The same Application ID and <span className="font-mono text-ink">private.key</span> are reused.
            </div>
            <button className="btn-ghost !py-2 !text-[12px]" disabled={busy === "voice" || !f.vonage_voice_to} onClick={async () => { setBusy("voice"); try { const r = await api<{ ok: boolean; message: string }>("/setup/test-voice", { method: "POST", json: { to: f.vonage_voice_to } }); push(r.ok ? "ok" : "err", r.message); } catch (e) { push("err", (e as Error).message); } setBusy(""); }}>
              {busy === "voice" ? "Calling…" : "Test phone call"}
            </button>
          </div>
        </FadeIn>
        <FadeIn delay={0.18}>
          <div className="card h-full space-y-3 p-5">
            <h2 className="text-sm font-bold text-ink">WhatsApp delivery architecture</h2>
            <div className="grid gap-2">
              {[
                ["01", "DETECT", "payment signal enters recovery"],
                ["02", "DIAGNOSE", "AI classifies grounded cause"],
                ["03", "DECIDE", "policy checks consent, timing and cost"],
                ["04", "ACT", "email / WhatsApp / voice dispatch"],
                ["05", "TRACK", "Provider status is written to the audit trail"],
              ].map(([n, title, text], i) => <div key={n} className="flex items-center gap-3 rounded-xl border border-line/60 bg-white/[.02] px-3 py-2.5">
                <span className="font-mono text-[9px] text-dim">{n}</span><span className="flow-node active"/><div><div className="text-[11px] font-semibold text-ink">{title}</div><div className="text-[10px] text-dim">{text}</div></div>{i < 4 ? <span className="ml-auto text-[10px] text-live">→</span> : null}
              </div>)}
            </div>
          </div>
        </FadeIn>
      </div>

      <FadeIn delay={0.2}>
        <div className="card p-5">
          <h2 className="mb-1 text-sm font-bold text-ink">Razorpay webhook (hosted events)</h2>
          <p className="mb-3 text-[12px] text-mute">Register this URL in <a className="text-brand2 hover:underline" href="https://dashboard.razorpay.com/app/settings/webhooks" target="_blank" rel="noreferrer">Razorpay → Settings → Webhooks ↗</a> (events: payment.captured, payment.failed, subscription.charged.failed) with the webhook secret saved above. Signature-verified (HMAC-SHA256) — unsigned requests get 401. Local run: <span className="font-mono text-ink">ngrok http 8000</span>.</p>
          <div className="flex items-center gap-2">
            <code className="flex-1 truncate rounded-xl border border-line2 bg-black/30 px-3 py-2 font-mono text-[12px] text-brand2">{typeof window !== "undefined" ? window.location.origin : ""}/api/v1/webhooks/razorpay</code>
            <button className="btn-ghost !py-2 !text-[12px]" onClick={() => { try { navigator.clipboard.writeText(`${window.location.origin}/api/v1/webhooks/razorpay`); push("ok", "Webhook URL copied"); } catch {} }}>Copy</button>
          </div>
        </div>
      </FadeIn>

      <FadeIn delay={0.18}>
        <button className="btn-primary" disabled={busy === "save"} onClick={save}>{busy === "save" ? "Saving…" : "Save settings"}</button>
      </FadeIn>
    </div>
  );
}
