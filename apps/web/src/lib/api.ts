"use client";

import { useQuery, UseQueryOptions } from "@tanstack/react-query";

const TOKEN_KEY = "rp_token";
const REFRESH_KEY = "rp_refresh";
const PORTAL_KEY = "rp_portal";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function authHeaders(): Record<string, string> {
  const h: Record<string, string> = {};
  try {
    const t = localStorage.getItem(TOKEN_KEY);
    if (t) h["x-rp-token"] = t;
    const p = localStorage.getItem(PORTAL_KEY);
    if (p) h["x-rp-portal"] = p;
  } catch {
    /* storage unavailable */
  }
  return h;
}

export function saveMerchantSession(token: string, refresh?: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
  } catch {}
}

export function savePortalSession(token: string): void {
  try {
    localStorage.setItem(PORTAL_KEY, token);
  } catch {}
}

export function clearSessions(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(PORTAL_KEY);
  } catch {}
}

export async function api<T = unknown>(path: string, init?: RequestInit & { json?: unknown }): Promise<T> {
  const { json, ...rest } = init ?? {};
  const request = (): Promise<Response> =>
    fetch(`/api/v1${path}`, {
      ...rest,
      credentials: "include",
      headers: {
        ...authHeaders(),
        ...(json !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(rest.headers ?? {}),
      },
      body: json !== undefined ? JSON.stringify(json) : rest.body,
    });

  let res = await request();

  // Access token expired → try one silent refresh (merchant), then retry.
  if (res.status === 401 && !path.startsWith("/auth/") && !path.startsWith("/portal/login") && !path.startsWith("/portal/register")) {
    const refresh = typeof window !== "undefined" ? localStorage.getItem(REFRESH_KEY) : null;
    const had = typeof window !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null;
    if (refresh && had) {
      try {
        const r = await fetch("/api/v1/auth/refresh", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh }),
        });
        if (r.ok) {
          const j = (await r.json()) as { token: string; refresh?: string };
          saveMerchantSession(j.token, j.refresh);
          res = await request();
        } else {
          clearSessions();
        }
      } catch {
        /* fall through with the 401 */
      }
    }
  }

  const text = await res.text();
  let data: unknown = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    // plain-text failures (proxy 500s, empty bodies) must not crash the client
    throw new ApiError(res.status, res.status >= 500 ? "Server error — try again in a moment" : text.slice(0, 140) || `Error ${res.status}`);
  }
  if (!res.ok) throw new ApiError(res.status, (data as { detail?: string }).detail ?? `Error ${res.status}`);
  return data as T;
}

/** Typed GET hook with sensible defaults. */
export function useApi<T>(key: unknown[], path: string, opts?: Omit<UseQueryOptions<T, ApiError>, "queryKey" | "queryFn">) {
  return useQuery<T, ApiError>({ queryKey: key, queryFn: () => api<T>(path), retry: false, ...opts });
}

export function fmtINR(paise: number, decimals = false): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency", currency: "INR",
    minimumFractionDigits: decimals ? 2 : 0, maximumFractionDigits: decimals ? 2 : 0,
  }).format(decimals ? paise / 100 : Math.floor(paise / 100));
}

export function fmtDT(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso.includes("T") ? iso : iso + "T00:00:00Z");
  return d.toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Kolkata" });
}

export function fmtD(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso.includes("T") ? iso : iso + "T00:00:00Z");
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: "Asia/Kolkata" });
}

export const STAGE_LABEL: Record<string, string> = {
  detected: "Detected", diagnosed: "Diagnosed", email_sent: "Email sent", promise_wait: "Promise hold",
  whatsapp_sent: "WhatsApp sent", voice_attempted: "Final attempt", recovered: "Recovered",
  escalated: "Escalated", stopped: "Stopped", closed: "Closed",
};

export const TYPE_LABEL: Record<string, string> = {
  payment_failed: "Payment failed", checkout_abandoned: "Checkout abandoned", subscription_failed: "Subscription failed",
  mandate_failed: "Mandate failed", invoice_overdue: "Invoice overdue",
};

export const CAUSE_LABEL: Record<string, string> = {
  soft_decline: "Soft decline", hard_decline: "Hard decline", gateway_technical: "Gateway / technical",
  voluntary_dropoff: "Voluntary drop-off", mandate_failure: "Mandate failure", b2b_nonpayment: "B2B non-payment",
};
