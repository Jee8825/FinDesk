"use client";
// Liquid Ledger FX — thin wrappers over @paper-design/shaders-react.
// All canvas shaders load client-side only (ssr:false) and freeze under
// prefers-reduced-motion. Aura trio: violet / teal / amber on deep void.
import { useReducedMotion } from "framer-motion";
import dynamic from "next/dynamic";

const MeshGradient = dynamic(
  () => import("@paper-design/shaders-react").then((m) => m.MeshGradient),
  { ssr: false },
);
const LiquidMetal = dynamic(
  () => import("@paper-design/shaders-react").then((m) => m.LiquidMetal),
  { ssr: false },
);
const PulsingBorder = dynamic(
  () => import("@paper-design/shaders-react").then((m) => m.PulsingBorder),
  { ssr: false },
);

export const AURA_COLORS = ["#0b0820", "#7c3aed", "#0ea5b7", "#f59e0b"];

/** Ambient aura — absolutely fills its (relative) parent, behind content. */
export function Aura({
  intensity = "page",
  className = "",
}: {
  /** page: quiet header wash · hero: login/share full-bleed · card: feature tile */
  intensity?: "page" | "hero" | "card";
  className?: string;
}) {
  const still = useReducedMotion();
  const speed = still ? 0 : intensity === "hero" ? 0.55 : 0.3;
  const opacity = intensity === "hero" ? 1 : intensity === "card" ? 0.55 : 0.42;
  return (
    <div
      aria-hidden
      className={`pointer-events-none absolute inset-0 overflow-hidden ${className}`}
      style={{ opacity }}
    >
      <MeshGradient
        colors={AURA_COLORS}
        distortion={0.9}
        swirl={0.25}
        speed={speed}
        style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
      />
      {/* fade the wash into the void so glass stays readable */}
      <div
        className="absolute inset-0"
        style={{
          background:
            intensity === "hero"
              ? "radial-gradient(120% 90% at 50% 16%, transparent 38%, rgba(6,10,18,0.72) 100%)"
              : "linear-gradient(180deg, rgba(6,10,18,0.2) 0%, rgba(6,10,18,0.9) 78%, #060a12 100%)",
        }}
      />
    </div>
  );
}

/** The liquid-metal F mark (liquid-logo technique via Paper Shaders). */
export function LiquidMark({ size = 40, className = "" }: { size?: number; className?: string }) {
  const still = useReducedMotion();
  return (
    <div
      aria-hidden
      className={`relative overflow-hidden rounded-[10px] ${className}`}
      style={{ width: size, height: size, background: "#0a0e1a", boxShadow: "inset 0 0 0 1px rgba(255,194,110,0.35)" }}
    >
      <LiquidMetal
        colorBack="#131a30"
        colorTint="#ffc26e"
        shape="diamond"
        distortion={0.08}
        repetition={1.6}
        softness={0.4}
        contour={0.35}
        angle={70}
        speed={still ? 0 : 0.5}
        style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
      />
      <span
        className="absolute inset-0 grid place-items-center font-display font-bold text-ink"
        style={{ fontSize: size * 0.52, textShadow: "0 1px 8px rgba(6,10,18,0.9)" }}
      >
        F
      </span>
    </div>
  );
}

/** Live ring — shader border pulse for the agent-health badge. */
export function LiveRing({
  live,
  size = 30,
  className = "",
}: {
  live: boolean;
  size?: number;
  className?: string;
}) {
  const still = useReducedMotion();
  return (
    <div aria-hidden className={`relative ${className}`} style={{ width: size, height: size }}>
      <PulsingBorder
        colors={live ? ["#43d695", "#2dd4bf", "#ffa028"] : ["#ff6e66", "#ff9c96"]}
        colorBack="#00000000"
        roundness={1}
        thickness={0.12}
        softness={0.6}
        intensity={live ? 0.28 : 0.15}
        speed={still || !live ? 0 : 1}
        style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
      />
      <span
        className={`absolute inset-[30%] rounded-full ${live ? "bg-moss" : "bg-claret"}`}
        style={{ boxShadow: live ? "0 0 12px rgba(67,214,149,0.8)" : "0 0 12px rgba(255,110,102,0.8)" }}
      />
    </div>
  );
}
