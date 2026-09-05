"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Logo } from "@/components/ui";

export function AuthShell({ title, sub, children, footer }: { title: string; sub: string; children: React.ReactNode; footer?: React.ReactNode }) {
  return (
    <main className="relative mx-auto flex min-h-screen w-full max-w-md flex-col justify-center px-6 py-12">
      <div aria-hidden className="pointer-events-none absolute left-1/2 top-16 h-72 w-72 -translate-x-1/2 rounded-full bg-brand/25 blur-[110px] animate-floaty" />
      <div aria-hidden className="pointer-events-none absolute bottom-10 right-0 h-56 w-56 rounded-full bg-fuchsia/15 blur-[100px] animate-floaty2" />

      <Link href="/" className="relative mb-8 flex justify-center">
        <motion.span initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
          <Logo size="lg" />
        </motion.span>
      </Link>

      <motion.div
        className="card ring-border relative p-8"
        initial={{ opacity: 0, y: 28, scale: 0.97, filter: "blur(6px)" }}
        animate={{ opacity: 1, y: 0, scale: 1, filter: "blur(0px)" }}
        transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      >
        <h1 className="display text-2xl font-bold tracking-tight text-ink">{title}</h1>
        <p className="mt-1.5 mb-7 text-[13px] leading-relaxed text-mute">{sub}</p>
        {children}
      </motion.div>
      {footer ? <div className="relative mt-6 text-center text-[13px] text-mute">{footer}</div> : null}
    </main>
  );
}

export function Err({ msg }: { msg: string }) {
  return msg ? (
    <motion.div initial={{ opacity: 0, y: -6, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }}
      className="rounded-xl border border-rose/30 bg-rose/10 px-3.5 py-2.5 text-[13px] text-rose">
      {msg}
    </motion.div>
  ) : null;
}
