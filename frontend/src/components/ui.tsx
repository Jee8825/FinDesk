"use client";
// FinDesk shared UI kit — "Liquid Ledger" system (design-v2).
// One dark void canvas; every surface is layered glass. The Surface context
// survives from the paper era: "light" = standard glass elevation, "dark" =
// deeper void (cash command). Pages keep their code; the kit changed under it.
import { HTMLMotionProps, motion, useSpring, useTransform } from "framer-motion";
import { createContext, useContext, useEffect } from "react";

import { Aura } from "@/components/fx";

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
  animate: { transition: { staggerChildren: 0.05 } },
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
  return <div className={`mono-label text-faint ${className}`}>{children}</div>;
}

export function Card({
  children,
  className = "",
  hover = false,
  ...rest
}: { children: React.ReactNode; className?: string; hover?: boolean } & HTMLMotionProps<"div">) {
  const deep = useSurface() === "dark";
  return (
    <motion.div
      variants={riseItem}
      whileHover={
        hover
          ? { y: -3, scale: 1.005, transition: { duration: 0.2 } }
          : undefined
      }
      className={`glass grain relative rounded-glass ${
        deep ? "border border-dark-line" : "border border-line2"
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
  const tones = {
    default: "text-ink",
    accent: "text-accent",
    good: "text-mint",
    bad: "text-blush",
  };
  return (
    <Card className="px-5 py-4" hover>
      <MonoLabel>{label}</MonoLabel>
      <div className={`tnum mt-2 font-mono text-[26px] font-semibold leading-none ${tones[tone]}`}>
        {typeof value === "number" && format ? (
          <AnimatedNumber value={value} format={format} />
        ) : (
          value
        )}
      </div>
      {sub && <div className="mt-2 text-xs text-faint">{sub}</div>}
    </Card>
  );
}

const PILL_TONES: Record<string, string> = {
  neutral: "bg-white/[0.04] text-mute border border-line2",
  good: "bg-moss/10 text-mint border border-moss/30",
  warn: "bg-accent/10 text-accent-soft border border-accent/30",
  bad: "bg-claret/10 text-blush border border-claret/30",
  memory: "bg-memory/15 text-memory border border-memory/40",
  ink: "bg-ink text-paper",
};

export function Pill({
  tone = "neutral",
  children,
  className = "",
}: {
  tone?: keyof typeof PILL_TONES;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-mono text-[10px] font-medium uppercase tracking-wider ${PILL_TONES[tone]} ${className}`}
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
  const fills = {
    accent: "bg-accent",
    good: "bg-moss",
    bad: "bg-claret",
    memory: "bg-memory",
  };
  return (
    <div className={`h-1.5 w-full overflow-hidden rounded-full bg-white/[0.07] ${className}`}>
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
      className={`${btnBase} bg-accent text-[#1a1204] shadow-[0_12px_28px_-10px_rgba(255,160,40,0.55)] hover:bg-accent-soft ${className}`}
      {...rest}
    />
  );
}

export function GhostBtn(props: HTMLMotionProps<"button">) {
  const { className = "", ...rest } = props;
  return (
    <motion.button
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.97 }}
      className={`${btnBase} glass border border-line text-mute hover:text-ink ${className}`}
      {...rest}
    />
  );
}

export function InkBtn(props: HTMLMotionProps<"button">) {
  const { className = "", ...rest } = props;
  return (
    <motion.button
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.97 }}
      className={`${btnBase} bg-ink text-paper hover:bg-white ${className}`}
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
  const deep = surface === "dark";
  return (
    <SurfaceCtx.Provider value={surface}>
      <div className="relative flex min-h-screen flex-1 flex-col">
        <header className="relative z-10 px-8 pb-0 pt-6">
          <Aura intensity="page" />
          <div className="relative flex items-end justify-between gap-6 pb-5">
            <div>
              <div className="flex items-center gap-3">
                <motion.h1
                  className="font-display text-[26px] font-bold tracking-[-0.01em] text-ink"
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.4 }}
                >
                  {title}
                </motion.h1>
                <span className="mono-label glass rounded-full border border-line2 px-2.5 py-1 text-faint">
                  {chip ?? (deep ? "cash command" : "ledger")}
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
          {/* the ledger beam — pulses while the agent is live (data-agent-live upstream) */}
          <div className="ledger-beam relative" />
        </header>
        <motion.div
          className={`relative flex-1 px-8 py-7 text-ink ${deep ? "bg-dark-bg/60" : ""}`}
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
  return <div className={`animate-pulse rounded-glass bg-white/[0.05] ${className}`} />;
}

export function EmptyState({
  children,
  hint,
}: {
  children: React.ReactNode;
  hint?: React.ReactNode;
}) {
  return (
    <motion.div
      {...rise}
      className="relative overflow-hidden rounded-glass border border-dashed border-line p-12 text-center text-sm text-mute"
    >
      <Aura intensity="card" />
      <div className="relative">{children}</div>
      {hint && <div className="mono-annot relative mt-3">{hint}</div>}
    </motion.div>
  );
}

export function ErrorNote({ children }: { children: React.ReactNode }) {
  return (
    <p className="mt-4 text-sm text-blush" role="alert">
      {children}
    </p>
  );
}
