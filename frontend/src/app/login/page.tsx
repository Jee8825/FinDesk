"use client";
// Login — sign-in card + the "Trust by Construction" promise panel.
import { motion } from "framer-motion";
import { ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { api, setTokens } from "@/lib/api";

const PROMISES = [
  "No money movement",
  "No external communication without approval",
  "Every action is explainable",
  "Every change is audited",
];

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("founder@demo.findesk.in");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setTokens(await api.login(email, password));
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-gradient-to-b from-[#efe8d6] to-paper p-6">
      <motion.div
        initial={{ opacity: 0, y: 24, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        className="grid w-full max-w-3xl overflow-hidden rounded-2xl border border-line2 bg-card shadow-card md:grid-cols-2"
      >
        <form onSubmit={submit} className="p-9">
          <div className="flex items-center gap-2.5">
            <div className="flex h-[34px] w-[34px] items-center justify-center rounded-[9px] border-2 border-ink text-base font-bold text-ink">
              F
            </div>
            <div>
              <div className="text-[15px] font-bold tracking-[-0.01em] text-ink">FinDesk</div>
              <div className="mono-label text-faint">autonomous cfo</div>
            </div>
          </div>
          <h1 className="mt-7 text-xl font-bold text-ink">Welcome back</h1>
          <p className="mt-1 text-sm text-mute">Sign in to your account.</p>

          <label className="mono-label mt-6 block text-faint" htmlFor="email">
            email
          </label>
          <input
            id="email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1.5 w-full rounded-lg border border-line bg-cream px-3 py-2.5 text-sm outline-none transition-colors focus:border-accent/60"
          />
          <label className="mono-label mt-4 block text-faint" htmlFor="password">
            password
          </label>
          <input
            id="password"
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1.5 w-full rounded-lg border border-line bg-cream px-3 py-2.5 text-sm outline-none transition-colors focus:border-accent/60"
          />
          {error && (
            <p className="mt-3 text-sm text-claret" role="alert">
              {error}
            </p>
          )}
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.97 }}
            type="submit"
            disabled={busy}
            className="mt-6 w-full rounded-lg bg-accent px-3 py-2.5 text-sm font-bold text-white shadow-[0_10px_24px_-10px_rgba(232,115,10,0.7)] transition-colors hover:bg-[#d96905] disabled:opacity-50"
          >
            {busy ? "Signing in…" : "Sign in"}
          </motion.button>
          <p className="mono-annot mt-5">◇ dev seed: founder@demo.findesk.in / demo1234 (make seed)</p>
        </form>

        <div className="hidden flex-col justify-center border-l border-line2 bg-gradient-to-b from-cream to-cream2 p-9 md:flex">
          <ShieldCheck className="text-accent" size={30} />
          <h2 className="mt-4 text-lg font-bold text-ink">Trust by Construction</h2>
          <p className="mt-1 text-[13px] leading-relaxed text-mute">
            It doesn&apos;t just close your books. It defends your cash — inside hard guardrails.
          </p>
          <ul className="mt-5 space-y-3">
            {PROMISES.map((p, i) => (
              <motion.li
                key={p}
                initial={{ opacity: 0, x: 14 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.25 + i * 0.12, duration: 0.4 }}
                className="flex items-center gap-2.5 text-[13.5px] font-semibold text-ink"
              >
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-moss/15 font-mono text-[11px] font-bold text-moss">
                  ✓
                </span>
                {p}
              </motion.li>
            ))}
          </ul>
        </div>
      </motion.div>
    </main>
  );
}
