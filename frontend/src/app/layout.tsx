import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono, Instrument_Sans, Space_Grotesk } from "next/font/google";

import "./globals.css";

// Liquid Ledger type trio: Space Grotesk carries display personality,
// Instrument Sans does quiet body work, IBM Plex Mono stays the ledger voice.
const display = Space_Grotesk({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-display",
  display: "swap",
});

const sans = Instrument_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-sans",
  display: "swap",
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "FinDesk — The Autonomous CFO",
  description: "Clean books. Defended cash. For Indian SMEs.",
};

export const viewport: Viewport = {
  themeColor: "#060a12",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${sans.variable} ${mono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
