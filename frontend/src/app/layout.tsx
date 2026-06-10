import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "FinDesk — The Autonomous CFO",
  description: "Clean books. Defended cash. For Indian SMEs.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
