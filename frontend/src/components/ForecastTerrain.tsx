"use client";
// 3D Cash Terrain — the design-v2 showpiece. The 13-week forecast as a
// landscape: upside/base/downside scenarios are terrain rows, height is
// closing balance, and the translucent claret plane is the ₹0 waterline —
// terrain dipping underwater is exactly a funding gap. Numbers all come
// from the backend forecast; this is presentation only.
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

import type { ForecastOut } from "@/lib/api";

const TerrainScene = dynamic(() => import("./ForecastTerrainScene"), {
  ssr: false,
  loading: () => (
    <div className="mt-4 grid h-[340px] w-full place-items-center rounded-glass bg-white/[0.03]">
      <span className="mono-label animate-pulse text-faint">building terrain…</span>
    </div>
  ),
});

function webglAvailable(): boolean {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") ?? c.getContext("webgl"));
  } catch {
    return false;
  }
}

export function ForecastTerrain({
  f,
  fallback,
}: {
  f: ForecastOut;
  fallback: React.ReactNode;
}) {
  const [mode, setMode] = useState<"pending" | "3d" | "2d">("pending");

  useEffect(() => {
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    setMode(!still && webglAvailable() ? "3d" : "2d");
  }, []);

  if (mode === "pending") {
    return <div className="mt-4 h-[340px] w-full animate-pulse rounded-glass bg-white/[0.03]" />;
  }
  if (mode === "2d") return <>{fallback}</>;

  return (
    <div>
      <TerrainScene f={f} />
      <div className="mt-2 flex items-center justify-between">
        <span className="mono-annot">
          ◇ drag to orbit · hover a week for drivers · the claret plane is the ₹0 waterline
        </span>
        <button
          onClick={() => setMode("2d")}
          className="mono-label rounded-full border border-line2 px-2.5 py-1 text-faint transition-colors hover:border-line hover:text-mute"
        >
          classic 2D
        </button>
      </div>
    </div>
  );
}
