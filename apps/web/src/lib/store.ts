"use client";

import { create } from "zustand";

export type Toast = { id: number; tone: "ok" | "err" | "info"; text: string };

type UIState = {
  toasts: Toast[];
  push: (tone: Toast["tone"], text: string) => void;
  dismiss: (id: number) => void;
};

export const useUI = create<UIState>((set) => ({
  toasts: [],
  push: (tone, text) => {
    const id = Date.now() + Math.random();
    set((s) => ({ toasts: [...s.toasts, { id, tone, text }] }));
    setTimeout(() => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })), 4200);
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));
