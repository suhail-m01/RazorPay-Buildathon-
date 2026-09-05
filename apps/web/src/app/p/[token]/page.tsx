"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { api, savePortalSession } from "@/lib/api";
import { Logo } from "@/components/ui";

export default function MagicLink({ params }: { params: { token: string } }) {
  const token = String(useParams()["token"]);
  const router = useRouter();
  const [state, setState] = useState<"working" | "error" | "needs-account">("working");
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    api<{ portal_token: string }>("/portal/exchange", { method: "POST", json: { token } })
      .then((r) => { savePortalSession(r.portal_token); router.replace("/portal"); })
      .catch((e) => setState(e.message.includes("portal account") ? "needs-account" : "error"));
  }, [token, router]);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 px-6">
      <Logo size="lg" />
      {state === "working" ? (
        <>
          <div className="skeleton h-3 w-48" />
          <p className="text-[13px] text-mute">Opening your secure payment page…</p>
        </>
      ) : state === "needs-account" ? (
        <div className="card max-w-sm p-6 text-center">
          <p className="text-[14px] font-semibold text-ink">One quick step</p>
          <p className="mt-2 text-[13px] leading-6 text-mute">Create your portal account with the same email, then the link will work instantly next time.</p>
          <a href="/portal/register" className="btn-primary mt-4 w-full">Create account →</a>
        </div>
      ) : (
        <div className="card max-w-sm p-6 text-center">
          <p className="text-[14px] font-semibold text-sla">Link expired</p>
          <p className="mt-2 text-[13px] leading-6 text-mute">Magic links live for 7 days. Ask the merchant team for a fresh one, or log in directly.</p>
          <a href="/portal/login" className="btn-ghost mt-4 w-full">Go to login</a>
        </div>
      )}
    </main>
  );
}
