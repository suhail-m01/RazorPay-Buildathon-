"use client";

import Link from "next/link";
import { FadeIn } from "@/lib/motion";
import { Logo } from "@/components/ui";
import { LandingRecoveryPreview } from "@/components/LandingRecoveryPreview";

export default function Landing() {
  return (
    <main className="premium-opening relative min-h-screen overflow-hidden">
      <LandingRecoveryPreview />

      <div className="relative z-20 mx-auto flex min-h-screen max-w-[1400px] flex-col px-5 sm:px-8 lg:px-10">
        <header className="flex items-center justify-between py-6">
          <Logo size="lg" />
          <nav className="flex items-center gap-2 text-[13px] sm:gap-4">
            <Link href="/portal/login" className="hidden text-mute transition-colors hover:text-ink sm:block">Customer portal</Link>
            <Link href="/login" className="btn-ghost !px-4 !py-2">Log in</Link>
            <Link href="/register" className="btn-primary opening-cta !px-4 !py-2">Get started</Link>
          </nav>
        </header>

        <section className="flex flex-1 items-center justify-center pb-20 pt-10 text-center sm:pb-24">
          <div className="mx-auto max-w-4xl">
            <FadeIn>
              <div className="opening-kicker mx-auto inline-flex items-center gap-2 rounded-full px-3.5 py-2 text-[10px] font-semibold uppercase tracking-[.2em]">
                <span className="opening-kicker-dot" /> Autonomous revenue recovery
              </div>
            </FadeIn>

            <FadeIn delay={0.08}>
              <h1 className="opening-title display mt-7 text-[3rem] font-bold leading-[.98] tracking-[-.05em] text-ink sm:text-[4.5rem] lg:text-[5.6rem]">
                Recover what matters.
                <br />
                <span>Automatically.</span>
              </h1>
            </FadeIn>

            <FadeIn delay={0.16}>
              <p className="opening-copy mx-auto mt-6 max-w-2xl text-[14px] leading-7 text-mute sm:text-[15px]">
                AI-guided diagnosis, deterministic policy controls and carefully bounded recovery actions — unified in one premium command center.
              </p>
            </FadeIn>

            <FadeIn delay={0.24} className="mt-8 flex flex-wrap items-center justify-center gap-3">
              <Link href="/register" className="btn-primary opening-cta !px-5 !py-3.5">Launch RecoverPay <span>↗</span></Link>
              <Link href="/login" className="btn-ghost opening-secondary !px-5 !py-3.5">Open command center <span>→</span></Link>
            </FadeIn>
          </div>
        </section>
      </div>
    </main>
  );
}
