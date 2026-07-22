import type { Config } from "tailwindcss";

// FinDesk design tokens — "Liquid Ledger" system (design-v2, dark-first).
// One deep void canvas; surfaces are layered glass. Token NAMES are kept from
// the ledger-paper era so existing pages inherit the reskin — VALUES are new.
// Aura color trio (violet/teal/amber) lives in shader components, not here.
const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Every value is a CSS var — :root carries dark, [data-theme="light"]
        // overrides in globals.css. Triplet vars keep /alpha utilities working.
        paper: "rgb(var(--c-paper) / <alpha-value>)",
        cream: "rgb(var(--c-cream) / <alpha-value>)",
        cream2: "rgb(var(--c-cream2) / <alpha-value>)",
        card: "rgb(var(--c-card) / <alpha-value>)",
        line: "var(--c-line)", // baked alpha per theme
        line2: "var(--c-line2)",
        ink: "rgb(var(--c-ink) / <alpha-value>)",
        mute: "rgb(var(--c-mute) / <alpha-value>)",
        faint: "rgb(var(--c-faint) / <alpha-value>)",
        annot: "rgb(var(--c-annot) / <alpha-value>)",
        accent: {
          DEFAULT: "rgb(var(--c-accent) / <alpha-value>)",
          soft: "rgb(var(--c-accent-soft) / <alpha-value>)",
        },
        moss: "rgb(var(--c-moss) / <alpha-value>)",
        mint: "rgb(var(--c-mint) / <alpha-value>)",
        claret: "rgb(var(--c-claret) / <alpha-value>)",
        blush: "rgb(var(--c-blush) / <alpha-value>)",
        memory: "rgb(var(--c-memory) / <alpha-value>)",
        dark: {
          bg: "rgb(var(--c-deep-bg) / <alpha-value>)",
          card: "rgb(var(--c-deep-card) / <alpha-value>)",
          card2: "rgb(var(--c-deep-card2) / <alpha-value>)",
          line: "var(--c-line)",
          text: "rgb(var(--c-ink) / <alpha-value>)",
          mute: "rgb(var(--c-deep-mute) / <alpha-value>)",
        },
        // legacy alias (pre-redesign pages) — keep until fully retired
        "teal-brand": "#2dd4bf",
      },
      fontFamily: {
        display: ["var(--font-display)", "ui-sans-serif", "system-ui", "sans-serif"],
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      boxShadow: {
        // depth on void — soft, wide, blue-black
        card: "0 24px 48px -24px rgba(2,6,16,0.9), 0 1px 0 0 rgba(255,255,255,0.06) inset",
        "card-dark": "0 24px 48px -24px rgba(0,0,0,0.95), 0 1px 0 0 rgba(255,255,255,0.05) inset",
        side: "8px 0 32px -16px rgba(2,6,16,0.9)",
        glow: "0 0 0 1px rgba(255,160,40,0.25), 0 12px 40px -12px rgba(255,160,40,0.35)",
      },
      backdropBlur: { glass: "18px" },
      borderRadius: { glass: "1.25rem" },
    },
  },
  plugins: [],
};
export default config;
