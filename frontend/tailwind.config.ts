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
        // canvas layers (was: warm paper)
        paper: "#060a12", // page void
        cream: "#0c1120", // shell / header glass fallback
        cream2: "#0a0e1a", // shell gradient end
        card: "#101527", // raised glass base
        line: "rgba(148,163,204,0.16)", // hairline on glass
        line2: "rgba(148,163,204,0.09)", // faint hairline
        // text
        ink: "#edf1fa", // primary text (inverted from paper era)
        mute: "#a6adc4", // secondary
        faint: "#6c7490", // tertiary
        annot: "#596180", // mono annotations
        // brand + status (lifted for dark AA)
        accent: { DEFAULT: "#ffa028", soft: "#ffc26e" }, // FinDesk amber
        moss: "#43d695", // success
        mint: "#7defc0", // success bright / on-glass
        claret: "#ff6e66", // danger
        blush: "#ff9c96", // danger soft
        memory: "#7ba3e8", // memory / belief blue
        dark: {
          // deeper-elevation namespace (kept for existing pages)
          bg: "#04070d",
          card: "#0d1222",
          card2: "#131a30",
          line: "rgba(148,163,204,0.14)",
          text: "#edf1fa",
          mute: "#8790aa",
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
