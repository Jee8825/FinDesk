import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0b1f33",
        teal: { brand: "#0e6e74" },
      },
    },
  },
  plugins: [],
};
export default config;
