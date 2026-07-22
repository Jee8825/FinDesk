"use client";
// The R3F scene behind ForecastTerrain. Loaded client-only (ssr:false).
// Perf notes: 13×3 heightfield = tiny geometry; refs mutated in useFrame
// (never setState there); autorotate pauses while the user hovers.
import { Grid, Html, Line, OrbitControls } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { useMemo, useRef, useState } from "react";
import * as THREE from "three";

import { formatINRCompact, type ForecastOut, type ForecastWeek } from "@/lib/api";

const ROW_Z = { upside: -1.7, base: 0, downside: 1.7 } as const;
const ROW_COLORS = {
  upside: new THREE.Color("#2dd4bf"),
  base: new THREE.Color("#ffa028"),
  downside: new THREE.Color("#a78bfa"),
} as const;
const SPAN_X = 13; // world units across the 13 weeks

type Rows = { upside: ForecastWeek[]; base: ForecastWeek[]; downside: ForecastWeek[]; whatif?: ForecastWeek[] };

function useScales(rows: Rows) {
  return useMemo(() => {
    const all = [...rows.upside, ...rows.base, ...rows.downside, ...(rows.whatif ?? [])].map(
      (w) => w.closing_paise,
    );
    const min = Math.min(0, ...all); // domain always includes the waterline
    const max = Math.max(0, ...all);
    const span = max - min || 1;
    const n = rows.base.length;
    const x = (i: number) => (n < 2 ? 0 : (i / (n - 1)) * SPAN_X - SPAN_X / 2);
    const y = (paise: number) => ((paise - min) / span) * 3 + 0.15;
    return { x, y, y0: y(0), n };
  }, [rows]);
}

function TerrainSurface({ rows }: { rows: Rows }) {
  const { x, y, n } = useScales(rows);
  const geometry = useMemo(() => {
    const order: ("upside" | "base" | "downside")[] = ["upside", "base", "downside"];
    const positions: number[] = [];
    const colors: number[] = [];
    order.forEach((k) => {
      rows[k].forEach((w, i) => {
        positions.push(x(i), y(w.closing_paise), ROW_Z[k]);
        const c = ROW_COLORS[k];
        colors.push(c.r, c.g, c.b);
      });
    });
    const indices: number[] = [];
    for (let r = 0; r < 2; r++) {
      for (let i = 0; i < n - 1; i++) {
        const a = r * n + i;
        const b = a + 1;
        const c = a + n;
        const d = c + 1;
        indices.push(a, c, b, b, c, d);
      }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    g.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
    g.setIndex(indices);
    g.computeVertexNormals();
    return g;
  }, [rows, x, y, n]);

  return (
    <mesh geometry={geometry}>
      <meshStandardMaterial
        vertexColors
        transparent
        opacity={0.32}
        roughness={0.35}
        metalness={0.4}
        side={THREE.DoubleSide}
        depthWrite={false}
      />
    </mesh>
  );
}

function Ridge({ rows, row }: { rows: Rows; row: "upside" | "base" | "downside" }) {
  const { x, y } = useScales(rows); // shared scale — rows must agree
  const weeks = rows[row];
  const points = useMemo(
    () => weeks.map((w, i) => new THREE.Vector3(x(i), y(w.closing_paise), ROW_Z[row])),
    [weeks, x, y, row],
  );
  return (
    <Line
      points={points}
      color={`#${ROW_COLORS[row].getHexString()}`}
      lineWidth={row === "base" ? 3 : 1.5}
      dashed={row !== "base"}
      dashSize={0.18}
      gapSize={0.12}
    />
  );
}

function WhatifRidge({ rows }: { rows: Rows }) {
  const { x, y } = useScales(rows);
  const points = useMemo(
    () => (rows.whatif ?? []).map((w, i) => new THREE.Vector3(x(i), y(w.closing_paise), 0.85)),
    [rows.whatif, x, y],
  );
  if (!points.length) return null;
  return (
    <Line points={points} color="#edf1fa" lineWidth={2} dashed dashSize={0.28} gapSize={0.14} />
  );
}

function GapBeacon({ f, rows }: { f: ForecastOut; rows: Rows }) {
  const { x, y } = useScales(rows);
  const ref = useRef<THREE.Mesh>(null);
  useFrame(({ clock }) => {
    if (!ref.current) return;
    const s = 1 + Math.sin(clock.elapsedTime * 3.2) * 0.25;
    ref.current.scale.setScalar(s);
  });
  if (!f.gap) return null;
  const wk = rows.downside.find((w) => w.week === f.gap!.week) ?? rows.base[f.gap.week - 1];
  if (!wk) return null;
  const i = rows.base.findIndex((w) => w.week === f.gap!.week);
  return (
    <group position={[x(i < 0 ? 0 : i), y(wk.closing_paise), ROW_Z.downside]}>
      <mesh ref={ref}>
        <sphereGeometry args={[0.14, 16, 16]} />
        <meshStandardMaterial
          color="#ff6e66"
          emissive="#ff6e66"
          emissiveIntensity={2}
          toneMapped={false}
        />
      </mesh>
      <pointLight color="#ff6e66" intensity={4} distance={3.2} />
    </group>
  );
}

function HoverColumns({
  rows,
  onHover,
}: {
  rows: Rows;
  onHover: (week: number | null) => void;
}) {
  const { x, n } = useScales(rows);
  return (
    <>
      {rows.base.map((w, i) => (
        <mesh
          key={w.week}
          position={[x(i), 1.8, 0]}
          onPointerOver={(e) => {
            e.stopPropagation();
            onHover(w.week);
          }}
          onPointerOut={() => onHover(null)}
          visible={false}
        >
          <boxGeometry args={[SPAN_X / Math.max(1, n - 1), 4.2, 4.4]} />
        </mesh>
      ))}
    </>
  );
}

function WeekTooltip({ f, rows, week }: { f: ForecastOut; rows: Rows; week: number }) {
  const { x, y } = useScales(rows);
  const i = rows.base.findIndex((w) => w.week === week);
  if (i < 0) return null;
  const base = rows.base[i];
  const up = rows.upside[i];
  const down = rows.downside[i];
  const isGap = f.gap?.week === week;
  return (
    <Html position={[x(i), y(up?.closing_paise ?? base.closing_paise) + 0.7, 0]} center zIndexRange={[40, 0]}>
      <div className="glass-strong pointer-events-none w-52 rounded-xl border border-line px-3 py-2.5 shadow-card">
        <div className="mono-label flex items-center justify-between text-faint">
          <span>week {week}</span>
          {isGap && <span className="text-blush">gap</span>}
        </div>
        <div className="mt-1.5 space-y-1 font-mono text-[11px]">
          <div className="flex justify-between text-[#2dd4bf]">
            <span>upside</span>
            <span className="tnum">{up ? formatINRCompact(up.closing_paise) : "—"}</span>
          </div>
          <div className="flex justify-between font-semibold text-accent">
            <span>base</span>
            <span className="tnum">{formatINRCompact(base.closing_paise)}</span>
          </div>
          <div className="flex justify-between text-[#a78bfa]">
            <span>downside</span>
            <span className="tnum">{down ? formatINRCompact(down.closing_paise) : "—"}</span>
          </div>
        </div>
        {base.drivers.length > 0 && (
          <div className="mono-annot mt-1.5 truncate">
            ◇ {base.drivers[0].client} {formatINRCompact(base.drivers[0].amount_paise)}
          </div>
        )}
      </div>
    </Html>
  );
}

function SceneInner({ f, whatif }: { f: ForecastOut; whatif?: ForecastWeek[] }) {
  const rows: Rows = useMemo(
    () => ({
      upside: f.scenarios.upside ?? [],
      base: f.scenarios.base ?? [],
      downside: f.scenarios.downside ?? [],
      whatif,
    }),
    [f, whatif],
  );
  const { y0 } = useScales(rows);
  const [hovered, setHovered] = useState<number | null>(null);

  return (
    <>
      <fog attach="fog" args={["#060a12", 14, 30]} />
      <ambientLight intensity={0.5} />
      <directionalLight position={[6, 10, 4]} intensity={1.1} />
      <pointLight position={[-8, 5, -6]} intensity={0.6} color="#7c3aed" />

      <TerrainSurface rows={rows} />
      <Ridge rows={rows} row="upside" />
      <Ridge rows={rows} row="base" />
      <Ridge rows={rows} row="downside" />
      <WhatifRidge rows={rows} />
      <GapBeacon f={f} rows={rows} />
      <HoverColumns rows={rows} onHover={setHovered} />
      {hovered !== null && <WeekTooltip f={f} rows={rows} week={hovered} />}

      {/* the ₹0 waterline — cash below this plane is a funding gap */}
      <mesh position={[0, y0, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[SPAN_X + 2, 5.6]} />
        <meshBasicMaterial color="#ff6e66" transparent opacity={0.07} side={THREE.DoubleSide} />
      </mesh>
      <Line
        points={[
          new THREE.Vector3(-SPAN_X / 2 - 1, y0, 2.8),
          new THREE.Vector3(SPAN_X / 2 + 1, y0, 2.8),
        ]}
        color="#ff6e66"
        lineWidth={1}
        transparent
        opacity={0.5}
      />

      <Grid
        position={[0, 0, 0]}
        args={[26, 26]}
        cellColor="#1c2440"
        sectionColor="#26314f"
        fadeDistance={24}
        fadeStrength={2}
        infiniteGrid
      />

      <OrbitControls
        makeDefault
        enablePan={false}
        enableDamping
        dampingFactor={0.08}
        minDistance={9}
        maxDistance={22}
        minPolarAngle={0.55}
        maxPolarAngle={1.42}
        autoRotate={hovered === null}
        autoRotateSpeed={0.45}
      />
    </>
  );
}

export default function ForecastTerrainScene({ f, whatif }: { f: ForecastOut; whatif?: ForecastWeek[] }) {
  return (
    <div className="mt-4 h-[340px] w-full overflow-hidden rounded-glass border border-line2 bg-[#04070d]">
      <Canvas dpr={[1, 2]} camera={{ position: [7.5, 5.5, 9.5], fov: 42 }}>
        <SceneInner f={f} whatif={whatif} />
      </Canvas>
    </div>
  );
}
