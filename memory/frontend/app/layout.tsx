import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Recall — Living Memory Dashboard",
  description: "Visualize memory decay, conflicts, and provenance in real time.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <div className="max-w-7xl mx-auto px-6 py-8">
          <header className="mb-8">
            <h1 className="text-3xl font-bold text-white">
              Recall <span className="text-accent">·</span>{" "}
              <span className="text-slate-400 text-xl font-normal">
                the memory layer that knows how to forget
              </span>
            </h1>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
