"use client";
// Login — liquid-glass gate. Full-bleed aura, glass card, liquid F-mark,
// and the trust promises the product is built on.
import { motion } from "framer-motion";
import { ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Aura, LiquidMark } from "@/components/fx";
import { api, setTokens } from "@/lib/api";

const PROMISES = [
  "No money movement",
  "No external communication without approval",
  "Every action is explainable",
  "Every change is audited",
];

const inputCls =
  "mt-1.5 w-full rounded-lg border border-line bg-white/[0.04] px-3 py-2.5 text-sm text-ink outline-none transition-colors placeholder:text-faint focus:border-accent/70 focus:bg-white/[0.06]";

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
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden p-6">
      <Aura intensity="hero" />

      <motion.div
        initial={{ opacity: 0, y: 24, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        className="glass-strong grain relative grid w-full max-w-3xl overflow-hidden rounded-glass border border-line md:grid-cols-2"
      >
        <form onSubmit={submit} className="p-9">
          <div className="flex items-center gap-2.5">
            <LiquidMark size={34} />
            <div>
              <div className="font-display text-[15px] font-bold tracking-[-0.01em] text-ink">
                FinDesk
              </div>
              <div className="mono-label text-faint">autonomous cfo</div>
            </div>
          </div>
          <h1 className="mt-7 font-display text-xl font-bold text-ink">Welcome back</h1>
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
            className={inputCls}
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
            className={inputCls}
          />
          {error && (
            <p className="mt-3 text-sm text-blush" role="alert">
              {error}
            </p>
          )}
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.97 }}
            type="submit"
            disabled={busy}
            className="mt-6 w-full rounded-lg bg-accent px-3 py-2.5 text-sm font-bold text-[#1a1204] shadow-[0_14px_32px_-10px_rgba(255,160,40,0.6)] transition-colors hover:bg-accent-soft disabled:opacity-50"
          >
            {busy ? "Signing in…" : "Sign in"}
          </motion.button>
          <p className="mono-annot mt-5">◇ dev seed: founder@demo.findesk.in / demo1234 (make seed)</p>
        </form>

        <div className="relative hidden flex-col justify-center overflow-hidden border-l border-line2 p-9 md:flex">
          <Aura intensity="card" />
          <div className="relative">
            <ShieldCheck className="text-accent" size={30} />
            <h2 className="mt-4 font-display text-lg font-bold text-ink">Trust by Construction</h2>
            <p className="mt-1 text-[13px] leading-relaxed text-mute">
              It doesn&apos;t just close your books. It defends your cash — inside hard guardrails.
            </p>
            <ul className="stagger-kids mt-5 space-y-3">
              {PROMISES.map((p) => (
                <li
                  key={p}
                  className="flex items-center gap-2.5 text-[13.5px] font-semibold text-ink"
                >
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-moss/15 font-mono text-[11px] font-bold text-mint">
                    ✓
                  </span>
                  {p}
                </li>
              ))}
            </ul>
            <div className="ledger-beam mt-7" />
          </div>
        </div>
      </motion.div>
    </main>
  );
}
