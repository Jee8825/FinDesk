"use client";
// FinDesk shared UI kit — the "ledger paper" system from the wireframes.
// Every consequential surface is either light (books, queues) or dark (cash
// command). Components read the surface from context so pages stay terse.
import { HTMLMotionProps, motion, useSpring, useTransform } from "framer-motion";
import { createContext, useContext, useEffect } from "react";

export type Surface = "light" | "dark";
const SurfaceCtx = createContext<Surface>("light");
export const useSurface = () => useContext(SurfaceCtx);

/* ---------------------------------------------------------------- motion */

export const rise = {
  initial: { opacity: 0, y: 14 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.45, ease: [0.22, 1, 0.36, 1] },
} as const;

export const stagger = {
  animate: { transition: { staggerChildren: 0.06 } },
} as const;

export const riseItem = {
  initial: { opacity: 0, y: 14 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.45, ease: [0.22, 1, 0.36, 1] } },
} as const;

/* ------------------------------------------------------------ primitives */

export function MonoLabel({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const dark = useSurface() === "dark";
  return (
    <div className={`mono-label ${dark ? "text-dark-mute" : "text-faint"} ${className}`}>
      {children}
    </div>
  );
}

export function Card({
  children,
  className = "",
  hover = false,
  ...rest
}: { children: React.ReactNode; className?: string; hover?: boolean } & HTMLMotionProps<"div">) {
  const dark = useSurface() === "dark";
  return (
    <motion.div
      variants={riseItem}
      whileHover={hover ? { y: -3, transition: { duration: 0.2 } } : undefined}
      className={`rounded-2xl border ${
        dark
          ? "border-dark-line bg-dark-card shadow-card-dark"
          : "border-line2 bg-card shadow-card"
      } ${className}`}
      {...rest}
    >
      {children}
    </motion.div>
  );
}

export function AnimatedNumber({ value, format }: { value: number; format: (n: number) => string }) {
  const spring = useSpring(0, { stiffness: 90, damping: 22 });
  const text = useTransform(spring, (v) => format(v));
  useEffect(() => {
    spring.set(value);
  }, [spring, value]);
  return <motion.span>{text}</motion.span>;
}

export function StatCard({
  label,
  value,
  sub,
  tone = "default",
  format,
}: {
  label: string;
  value: string | number;
  sub?: React.ReactNode;
  tone?: "default" | "accent" | "good" | "bad";
  format?: (n: number) => string;
}) {
  const dark = useSurface() === "dark";
  const tones = dark
    ? { default: "text-dark-text", accent: "text-accent-soft", good: "text-mint", bad: "text-blush" }
    : { default: "text-ink", accent: "text-accent", good: "text-moss", bad: "text-claret" };
  return (
    <Card className="px-5 py-4" hover>
      <MonoLabel>{label}</MonoLabel>
      <div className={`mt-2 font-mono text-[26px] font-semibold leading-none ${tones[tone]}`}>
        {typeof value === "number" && format ? (
          <AnimatedNumber value={value} format={format} />
        ) : (
          value
        )}
      </div>
      {sub && (
        <div className={`mt-2 text-xs ${dark ? "text-dark-mute" : "text-faint"}`}>{sub}</div>
      )}
    </Card>
  );
}

const PILL_TONES_LIGHT: Record<string, string> = {
  neutral: "bg-line2 text-mute",
  good: "bg-moss/10 text-moss border border-moss/25",
  warn: "bg-accent/10 text-accent border border-accent/25",
  bad: "bg-claret/10 text-claret border border-claret/25",
  memory: "bg-memory/10 text-memory border border-memory/25",
  ink: "bg-ink text-cream",
};
const PILL_TONES_DARK: Record<string, string> = {
  neutral: "bg-dark-card2 text-dark-mute border border-dark-line",
  good: "bg-mint/10 text-mint border border-mint/25",
  warn: "bg-accent/15 text-accent-soft border border-accent/30",
  bad: "bg-blush/10 text-blush border border-blush/25",
  memory: "bg-memory/20 text-[#9db8dd] border border-memory/40",
  ink: "bg-dark-text text-ink",
};

export function Pill({
  tone = "neutral",
  children,
  className = "",
}: {
  tone?: keyof typeof PILL_TONES_LIGHT;
  children: React.ReactNode;
  className?: string;
}) {
  const dark = useSurface() === "dark";
  const tones = dark ? PILL_TONES_DARK : PILL_TONES_LIGHT;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-mono text-[10px] font-medium uppercase tracking-wider ${tones[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

export function Bar({
  pct,
  tone = "accent",
  className = "",
}: {
  pct: number;
  tone?: "accent" | "good" | "bad" | "memory";
  className?: string;
}) {
  const dark = useSurface() === "dark";
  const fills = {
    accent: "bg-accent",
    good: dark ? "bg-mint" : "bg-moss",
    bad: dark ? "bg-blush" : "bg-claret",
    memory: "bg-memory",
  };
  return (
    <div className={`h-1.5 w-full overflow-hidden rounded-full ${dark ? "bg-dark-line" : "bg-line2"} ${className}`}>
      <motion.div
        className={`h-full rounded-full ${fills[tone]}`}
        initial={{ width: 0 }}
        animate={{ width: `${Math.max(0, Math.min(100, pct))}%` }}
        transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
      />
    </div>
  );
}

/* --------------------------------------------------------------- buttons */

const btnBase =
  "inline-flex items-center justify-center gap-1.5 rounded-lg px-4 py-2 text-sm font-semibold transition-colors disabled:opacity-50 disabled:pointer-events-none";

export function PrimaryBtn(props: HTMLMotionProps<"button">) {
  const { className = "", ...rest } = props;
  return (
    <motion.button
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.97 }}
      className={`${btnBase} bg-accent text-white shadow-[0_10px_24px_-10px_rgba(232,115,10,0.7)] hover:bg-[#d96905] ${className}`}
      {...rest}
    />
  );
}

export function GhostBtn(props: HTMLMotionProps<"button">) {
  const dark = useSurface() === "dark";
  const { className = "", ...rest } = props;
  return (
    <motion.button
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.97 }}
      className={`${btnBase} border ${
        dark
          ? "border-dark-line bg-transparent text-dark-text hover:bg-dark-card2"
          : "border-line bg-transparent text-mute hover:bg-cream"
      } ${className}`}
      {...rest}
    />
  );
}

export function InkBtn(props: HTMLMotionProps<"button">) {
  const dark = useSurface() === "dark";
  const { className = "", ...rest } = props;
  return (
    <motion.button
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.97 }}
      className={`${btnBase} ${
        dark ? "bg-dark-text text-ink hover:bg-white" : "bg-ink text-cream hover:bg-black"
      } ${className}`}
      {...rest}
    />
  );
}

/* ------------------------------------------------------------ page shell */

export function PageShell({
  title,
  chip,
  subtitle,
  annotation,
  surface = "light",
  actions,
  children,
}: {
  title: string;
  chip?: string;
  subtitle?: string;
  annotation?: string;
  surface?: Surface;
  actions?: React.ReactNode;
  children: React.ReactNode;
}) {
  const dark = surface === "dark";
  return (
    <SurfaceCtx.Provider value={surface}>
      <div className="flex min-h-screen flex-1 flex-col">
        <header className="border-b border-line bg-gradient-to-b from-cream to-[#f6f0e3] px-8 pb-5 pt-6">
          <div className="flex items-end justify-between gap-6">
            <div>
              <div className="flex items-center gap-3">
                <motion.h1
                  className="text-[26px] font-bold tracking-[-0.01em] text-ink"
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.4 }}
                >
                  {title}
                </motion.h1>
                <span
                  className={`mono-label rounded-full border px-2.5 py-1 ${
                    dark
                      ? "border-ink bg-ink text-cream"
                      : "border-line bg-cream text-faint"
                  }`}
                >
                  {chip ?? (dark ? "dark surface" : "light surface")}
                </span>
              </div>
              {subtitle && <p className="mt-1 text-sm text-mute">{subtitle}</p>}
            </div>
            <div className="flex items-center gap-3">
              {actions}
              {annotation && (
                <span className="mono-annot hidden xl:block">◇ {annotation}</span>
              )}
            </div>
          </div>
        </header>
        <motion.div
          className={`flex-1 px-8 py-7 ${
            dark
              ? "bg-dark-bg text-dark-text"
              : "bg-gradient-to-b from-[#efe8d6] to-paper text-ink"
          }`}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.35 }}
        >
          {children}
        </motion.div>
      </div>
    </SurfaceCtx.Provider>
  );
}

/* ----------------------------------------------------------- data states */

export function Skeleton({ className = "" }: { className?: string }) {
  const dark = useSurface() === "dark";
  return (
    <div
      className={`animate-pulse rounded-2xl ${dark ? "bg-dark-card2" : "bg-[#efe9db]"} ${className}`}
    />
  );
}

export function EmptyState({
  children,
  hint,
}: {
  children: React.ReactNode;
  hint?: React.ReactNode;
}) {
  const dark = useSurface() === "dark";
  return (
    <motion.div
      {...rise}
      className={`rounded-2xl border-2 border-dashed p-12 text-center text-sm ${
        dark ? "border-dark-line text-dark-mute" : "border-[#ccc7bb] text-faint"
      }`}
    >
      <div>{children}</div>
      {hint && <div className="mono-annot mt-3">{hint}</div>}
    </motion.div>
  );
}

export function ErrorNote({ children }: { children: React.ReactNode }) {
  const dark = useSurface() === "dark";
  return (
    <p className={`mt-4 text-sm ${dark ? "text-blush" : "text-claret"}`} role="alert">
      {children}
    </p>
  );
}
