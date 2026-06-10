import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0b1726",
        panel: "#0f2133",
        accent: "#38bdf8",
        episodic: "#f59e0b",
        semantic: "#38bdf8",
        procedural: "#a3e635",
      },
    },
  },
  plugins: [],
};

export default config;
