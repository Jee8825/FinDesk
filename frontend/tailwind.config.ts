import type { Config } from "tailwindcss";

// FinDesk design tokens — "ledger paper" system from FinDesk Wireframes.dc.html.
// Light surfaces (books/queues) sit on warm cream; dark surfaces (cash command)
// on deep warm black. Accent is burnt orange; mono labels do the annotating.
const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#e6dbc5", // page canvas
        cream: "#fcf9f2", // sidebar / header top
        cream2: "#f4eee2", // sidebar gradient end
        card: "#fdfbf5", // light-surface card
        line: "#e2dccd", // light borders
        line2: "#eeeae1",
        ink: "#26241f", // primary text / active nav pill
        mute: "#55514a", // secondary text
        faint: "#9b968a", // tertiary text
        annot: "#a49e90", // mono annotations
        accent: { DEFAULT: "#e8730a", soft: "#e8a868" }, // burnt orange
        moss: "#3f7d4e", // success on light
        mint: "#9fd2c0", // success on dark
        claret: "#b0433a", // danger on light
        blush: "#e8a3a0", // danger on dark
        memory: "#4a6fa5", // "memory / existing belief" blue
        dark: {
          bg: "#211f1b", // dark-surface content area
          card: "#262420",
          card2: "#2b2925",
          line: "#2e2c28",
          text: "#f0eee8",
          mute: "#7d7a72",
        },
        // legacy alias (pre-redesign pages) — keep until fully retired
        "teal-brand": "#0e6e74",
      },
      fontFamily: {
        sans: ["var(--font-plex-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-plex-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      boxShadow: {
        card: "0 18px 40px -24px rgba(120,106,70,0.45)",
        "card-dark": "0 18px 40px -24px rgba(0,0,0,0.6)",
        side: "6px 0 24px -12px rgba(120,106,70,0.4)",
      },
    },
  },
  plugins: [],
};
export default config;
