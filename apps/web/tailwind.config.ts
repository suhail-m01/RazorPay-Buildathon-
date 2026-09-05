import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#05060A",
        card: "#0C0E14",
        card2: "#12141D",
        line: "#1E2130",
        line2: "#2A2E42",
        ink: "#F2F3F8",
        mute: "#9BA3B7",
        dim: "#5D6478",
        brand: "#9F906C",          // deep indigo
        brand2: "#CDBF9D",         // muted violet
        fuchsia: "#77715F",        // reserved (kept for compat, now quiet)
        cyan: "#A7B2AA",           // subtle cyan
        lime: "#A5BBAE",           // muted emerald
        rose: "#B9A59E",           // soft rose
        amber: "#C8B98F",          // champagne
        champagne: "#D6C8A5",
        // legacy aliases (kept so existing pages keep working)
        live: "#A5BBAE",
        sla: "#B9A59E",
        warn: "#C8B98F",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["var(--font-grotesk)", "var(--font-inter)", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      boxShadow: {
        glow: "0 0 48px -16px rgba(214,200,165,.22)",
        glowpink: "0 0 48px -16px rgba(167,178,170,.18)",
        neon: "0 0 20px -8px rgba(165,187,174,.20)",
        card: "0 1px 0 0 rgba(255,255,255,.04) inset, 0 24px 48px -24px rgba(0,0,0,.7)",
        lift: "0 16px 40px -16px rgba(0,0,0,.8)",
      },
      keyframes: {
        shimmer: { "0%": { backgroundPosition: "-400px 0" }, "100%": { backgroundPosition: "400px 0" } },
        floaty: {
          "0%, 100%": { transform: "translate3d(0,0,0) scale(1)" },
          "50%": { transform: "translate3d(30px,-40px,0) scale(1.15)" },
        },
        floaty2: {
          "0%, 100%": { transform: "translate3d(0,0,0) scale(1.1)" },
          "50%": { transform: "translate3d(-40px,30px,0) scale(0.95)" },
        },
        marquee: { "0%": { transform: "translateX(0)" }, "100%": { transform: "translateX(-50%)" } },
        spinSlow: { to: { transform: "rotate(360deg)" } },
        pulseDot: { "0%,100%": { opacity: "1", transform: "scale(1)" }, "50%": { opacity: ".35", transform: "scale(.75)" } },
      },
      animation: {
        floaty: "floaty 18s ease-in-out infinite",
        floaty2: "floaty2 22s ease-in-out infinite",
        marquee: "marquee 30s linear infinite",
        spinSlow: "spinSlow 14s linear infinite",
        pulseDot: "pulseDot 1.6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
