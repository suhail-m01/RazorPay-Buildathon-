"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { PulseDot, EASE } from "@/components/motion";
import { api, clearSessions } from "@/lib/api";
import { Logo, LivePill } from "@/components/ui";
import clsx from "clsx";

const NAV = [
  { href: "/app", label: "Overview", icon: "◈" },
  { href: "/app/cases", label: "Recovery cases", icon: "❐" },
  { href: "/app/batch", label: "Batches", icon: "▤" },
  { href: "/app/agent", label: "AI Agent", icon: "✦" },
  { href: "/app/analytics", label: "Analytics", icon: "◒" },
  { href: "/app/approvals", label: "Approvals", icon: "✓" },
  { href: "/app/audit", label: "Decision trace", icon: "☰" },
  { href: "/app/payments", label: "Payment requests", icon: "⚡" },
  { href: "/app/playbooks", label: "Playbooks", icon: "◇" },
  { href: "/app/settings", label: "Settings", icon: "⚙" },
];

function useIstClock() {
  const [now, setNow] = useState("");
  useEffect(() => {
    const fmt = () =>
      new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit", timeZone: "Asia/Kolkata" });
    setNow(fmt());
    const t = setInterval(() => setNow(fmt()), 1000);
    return () => clearInterval(t);
  }, []);
  return now;
}

export function MerchantShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [me, setMe] = useState<{ name: string; email: string; merchant: string; role: string } | null>(null);
  const [checked, setChecked] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const clock = useIstClock();

  useEffect(() => {
    api<{ name: string; email: string; merchant: string; role: string }>("/auth/me")
      .then(setMe)
      .catch(() => router.replace("/login"))
      .finally(() => setChecked(true));
  }, [router]);

  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  async function logout() {
    clearSessions();
    await api("/auth/logout", { method: "POST" }).catch(() => {});
    router.push("/login");
  }

  if (!checked) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="h-10 w-10 rounded-full border-2 border-line2 border-t-brand2 animate-spin" />
          <span className="grad-text display text-lg font-bold">RecoverPay</span>
        </div>
      </div>
    );
  }
  if (!me) return null;

  const initials = me.name.split(" ").map((p) => p[0]).join("").slice(0, 2);

  return (
    <div className="min-h-screen lg:flex">
      {/* ---------- sidebar ---------- */}
      <aside className="sticky top-0 z-30 hidden h-screen w-60 shrink-0 flex-col border-r border-line/70 bg-card/60 backdrop-blur-xl lg:flex">
        <div className="px-5 py-6">
          <Link href="/app"><Logo size="lg" /></Link>
          <div className="mt-2 flex items-center gap-2 text-[11px] text-dim">
            <LivePill live={false} />
            <span className="truncate">{me.merchant}</span>
          </div>
        </div>
        <nav className="flex-1 space-y-0.5 px-3">
          {NAV.map((n, i) => {
            const active = n.href === "/app" ? pathname === "/app" : pathname.startsWith(n.href);
            return (
              <motion.div key={n.href} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.03 * i, duration: 0.35, ease: EASE }}>
                <Link href={n.href}
                  className={clsx("group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium transition-colors", active ? "text-ink" : "text-mute hover:text-ink")}>
                  {active && (
                    <motion.span layoutId="navActive" className="absolute inset-0 rounded-xl border border-brand2/25 bg-white/[.05]"
                      transition={{ type: "spring", stiffness: 380, damping: 32 }} />
                  )}
                  {active && (
                    <motion.span layoutId="navRail" className="absolute left-0 top-[22%] bottom-[22%] w-[3px] rounded-full"
                      style={{ background: "linear-gradient(180deg,#EEE3C8,#A99B79)", boxShadow: "0 0 12px rgba(214,200,165,.45)" }}
                      transition={{ type: "spring", stiffness: 380, damping: 32 }} />
                  )}
                  <motion.span className="relative w-4 text-center text-[13px]" whileHover={{ x: 1.5 }} transition={{ duration: 0.18 }}
                    style={{ color: active ? undefined : "#5D6478" }}>
                    <span className={active ? "grad-text" : "group-hover:text-mute transition-colors"}>{n.icon}</span>
                  </motion.span>
                  <span className="relative">{n.label}</span>
                </Link>
              </motion.div>
            );
          })}
        </nav>
        <div className="border-t border-line/70 p-3">
          <button
            onClick={() => setMenuOpen((v) => !v)}
            className="flex w-full items-center gap-3 rounded-xl px-2.5 py-2 text-left transition-colors hover:bg-white/[.04]"
          >
            <motion.span whileHover={{ scale: 1.06 }} whileTap={{ scale: 0.96 }} transition={{ type: "spring", stiffness: 400, damping: 20 }} className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-brand to-fuchsia text-[12px] font-bold text-white shadow-glow">
              {initials}
            </motion.span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[13px] font-semibold text-ink">{me.name}</span>
              <span className="block truncate text-[11px] capitalize text-dim">{me.role}</span>
            </span>
            <span className="text-dim">⌄</span>
          </button>
          <AnimatePresence>
            {menuOpen && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="overflow-hidden"
              >
                <motion.button onClick={logout} initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="btn-danger mt-2 w-full !py-2 !text-[12px]">Log out</motion.button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </aside>

      {/* ---------- main ---------- */}
      <div className="min-w-0 flex-1">
        {/* top bar */}
        <header className="sticky top-0 z-20 border-b border-line/70 bg-canvas/70 backdrop-blur-xl">
          <div className="flex h-14 items-center gap-3 px-5">
            <Link href="/app" className="lg:hidden"><Logo /></Link>
            <div className="hidden items-center gap-2 lg:flex">
              <span className="pill pill-cyan">IST {clock}</span>
              <span className="text-[12px] text-dim">· quiet hours guard active 21:00–09:00</span>
            </div>
            <div className="ml-auto flex items-center gap-2">
              <span className="pill pill-live"><PulseDot size={5} /> fast-sync 10s</span>
              {/* mobile logout */}
              <button onClick={logout} className="btn-ghost !px-3 !py-1.5 !text-[12px] lg:hidden">Log out</button>
              <button
                onClick={() => setMenuOpen((v) => !v)}
                ref={undefined}
                className="hidden h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-brand to-fuchsia text-[12px] font-bold text-white shadow-glow lg:flex"
                title={`${me.name} · ${me.role}`}
              >
                {initials}
              </button>
            </div>
          </div>
          {/* mobile nav */}
          <nav className="flex gap-1 overflow-x-auto px-4 pb-3 lg:hidden">
            {NAV.map((n) => {
              const active = n.href === "/app" ? pathname === "/app" : pathname.startsWith(n.href);
              return (
                <Link key={n.href} href={n.href} className={clsx("pill whitespace-nowrap", active ? "pill-brand" : "pill-mute")}>
                  {n.label}
                </Link>
              );
            })}
          </nav>
        </header>

        {/* top-right dropdown (avatar) */}
        <AnimatePresence>
          {menuOpen && (
            <motion.div
              ref={menuRef}
              initial={{ opacity: 0, y: -8, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -8, scale: 0.97 }}
              className="fixed right-5 top-16 z-40 w-60 rounded-2xl border border-line2 bg-card/95 p-4 shadow-lift backdrop-blur-xl"
            >
              <div className="text-[13px] font-semibold text-ink">{me.name}</div>
              <div className="truncate text-[11px] text-dim">{me.email}</div>
              <div className="my-3 h-px bg-line" />
              <button onClick={logout} className="btn-danger w-full !py-2 !text-[12px]">Log out</button>
            </motion.div>
          )}
        </AnimatePresence>

        <main className="mx-auto max-w-7xl px-5 py-7">{children}</main>
      </div>
    </div>
  );
}
