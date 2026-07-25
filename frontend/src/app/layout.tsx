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
  title: "LeakRadar — Find the money leaving quietly",
  description:
    "Detects every recurring payment, the price hikes nobody noticed, and what each one really costs you a year. Built on the FinDesk engine.",
};

export const viewport: Viewport = {
  themeColor: "#060a12",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${sans.variable} ${mono.variable}`}>
      <head>
        {/* theme before paint — no flash; dark is the default */}
        <script
          dangerouslySetInnerHTML={{
            __html:
              "try{if(localStorage.getItem('fd-theme')==='light')document.documentElement.dataset.theme='light'}catch(e){}",
          }}
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
