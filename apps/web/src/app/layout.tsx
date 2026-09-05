import type { Metadata } from "next";
import { Inter, Space_Grotesk } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/Providers";
import { Toaster } from "@/components/ui";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const grotesk = Space_Grotesk({ subsets: ["latin"], variable: "--font-grotesk", weight: ["400", "500", "600", "700"], display: "swap" });

export const metadata: Metadata = {
  title: "RecoverPay AI — Autonomous Revenue Recovery",
  description: "An AI agent that detects revenue at risk, determines the right intervention, and executes a bounded recovery workflow.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${grotesk.variable}`}>
      <body className="min-h-screen">
        {/* ambient scene — aurora orbs + fine grain */}
        <div className="scene" aria-hidden>
          <div className="orb orb-a" />
          <div className="orb orb-b" />
          <div className="orb orb-c" />
        </div>
        <div className="grain" aria-hidden />
        <Providers>
          {children}
          <Toaster />
        </Providers>
      </body>
    </html>
  );
}
