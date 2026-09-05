"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { Logo } from "@/components/ui";
import { FadeIn, motion } from "@/lib/motion";
import { SuccessCheck } from "@/components/motion";
import { useUI } from "@/lib/store";

type Info = { amount_paise: number; key_id: string; checkout_live: boolean; customer_name: string };

export default function PayPage() {
  const orderId = String(useParams()["orderId"]);
  const push = useUI((s) => s.push);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [info, setInfo] = useState<Info | null>(null);
  const [err, setErr] = useState("");

  const isRzp = orderId.startsWith("order_") && !orderId.startsWith("order_local");
  const rupees = (p: number) => `₹${(p / 100).toLocaleString("en-IN")}`;

  async function loadInfo(): Promise<Info | null> {
    if (info) return info;
    const i = await api<Info>(`/pay/${orderId}/info`);
    setInfo(i);
    return i;
  }

  async function payRzp() {
    setBusy(true);
    setErr("");
    try {
      let i = info;
      if (!i) {
        i = await api<Info>(`/pay/${orderId}/info`);
        setInfo(i);
      }
      if (!i.checkout_live || !i.key_id) throw new Error("Checkout unavailable — ask the merchant to connect Razorpay.");
      await new Promise<void>((res, rej) => {
        const s = document.createElement("script");
        s.src = "https://checkout.razorpay.com/v1/checkout.js";
        s.onload = () => res();
        s.onerror = () => rej(new Error("Could not load Razorpay checkout"));
        document.body.appendChild(s);
      });
      const w = window as unknown as { Razorpay: new (o: Record<string, unknown>) => { open: () => void } };
      const rzp = new w.Razorpay({
        key: i.key_id,
        amount: i.amount_paise,
        currency: "INR",
        name: "RecoverPay AI",
        description: "Payment",
        order_id: orderId,
        prefill: { name: i.customer_name },
        theme: { color: "#A99B79" },
        modal: {
          ondismiss: () => setBusy(false),
        },
        handler: async (resp: { razorpay_order_id: string; razorpay_payment_id: string; razorpay_signature: string }) => {
          try {
            await api("/pay/complete", { method: "POST", json: resp });
            setDone(true);
            push("ok", "Payment captured");
          } catch (e) {
            setErr((e as Error).message);
          }
          setBusy(false);
        },
      });
      rzp.open();
    } catch (e) {
      const msg = (e as Error).message;
      setErr(msg.includes("checkout")
        ? "Razorpay checkout can't load inside an embedded preview. Open this page in a normal browser tab (↗ on the preview panel) — or run the app locally — and pay from there."
        : msg);
      setBusy(false);
    }
  }

  async function payLocal() {
    setBusy(true);
    setErr("");
    try {
      await api("/portal/checkout", { method: "POST", json: { order_id: orderId } });
      setDone(true);
      push("ok", "Payment captured");
    } catch (e) {
      setErr((e as Error).message);
    }
    setBusy(false);
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-md flex-col justify-center px-6 py-10">
      <div className="mb-6 flex items-center justify-between">
        <Logo size="lg" />
        {isRzp ? <span className="pill bg-live/10 text-live ring-1 ring-live/25">RAZORPAY SECURE</span>
               : <span className="pill bg-warn/10 text-warn ring-1 ring-warn/25">TEST MODE</span>}
      </div>
      <FadeIn>
        <div className="card p-6">
          {done ? (
            <div className="py-6 text-center">
              <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-[#3ECFA5]/10 text-2xl text-[#7CD4B4]"><SuccessCheck size={26} /></div>
              <div className="display text-lg font-bold text-ink">Payment received</div>
              <p className="mt-2 text-[13px] text-mute">Your receipt is on its way by email. You can close this page.</p>
            </div>
          ) : (
            <>
              <div className="label">Order</div>
              <div className="font-mono text-[13px] text-mute">{orderId}</div>
              <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, ease: [0.22,1,0.36,1] }} className="mt-5 rounded-xl border border-[#D8C9A3]/15 bg-black/30 p-5 text-center s4">
                <div className="text-[10px] font-medium uppercase tracking-[.22em] text-dim">Amount payable</div>
                <div className="display num-hero mt-1.5 text-4xl font-semibold grad-text">{info ? rupees(info.amount_paise) : "…"}</div>
              </motion.div>
              <button className="btn-primary mt-5 w-full !py-3.5 !text-base" disabled={busy} onClick={isRzp ? payRzp : payLocal}>
                {busy ? "Opening checkout…" : "Pay now"}
              </button>
              {err ? <p className="mt-3 text-center text-[12px] text-sla">{err}</p> : null}
              <p className="mt-4 text-center text-[11px] leading-5 text-dim">
                {isRzp
                  ? "Secure checkout by Razorpay. Test mode: use card 4111 1111 1111 1111 (succeeds) or 4000 0000 0000 0002 (declines)."
                  : "Runs the same capture path as a live Razorpay webhook."}
              </p>
            </>
          )}
        </div>
      </FadeIn>
    </main>
  );
}
