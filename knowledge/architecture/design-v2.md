---
title: design-v2
type: note
permalink: findesk/architecture/design-v2
---

# Design v2 — "Liquid Ledger" (liquid-glass fintech, dark-first)

Decision record for the full reskin (branch `feat/design-v2`, started
2026-07-22). Supersedes the ledger-paper system described in
[[frontend-ui]] (kept for the light theme revival later).

## Direction (user-locked, 8-question round)
- **Scope**: full reskin, all pages; IA/navigation unchanged
- **Aesthetic**: liquid-glass fintech — glassmorphic panels, shader auras,
  liquid F-mark, layered translucent shades
- **Theme**: dark-first; tokens structured so light is a follow-up
- **3D**: ambient (login/dashboard/empty states) + ONE functional
  showpiece (3D Cash Terrain on Forecast)
- **Motion**: expressive but purposeful (springs, staggers, animated
  numbers; 120fps discipline, `prefers-reduced-motion` everywhere)
- **Features**: ⌘K Command Palette · 3D Cash Terrain · Daily CFO Brief ·
  Scenario Sandbox (contract-first `/forecast/whatif`)

## Research outcomes (2026-07-22)
- **@shadergradient/react 2.4.20** — R3F-based animated gradients; needs
  fiber+three+three-stdlib+camera-controls. Heavier than needed for
  ambient use → NOT chosen for page backgrounds.
- **@paper-design/shaders-react 0.0.77** (Apache-2.0, from the
  liquid-logo authors) — zero-dep canvas shaders as plain React
  components (`MeshGradient`, `DotOrbit`, more at shaders.paper.design).
  → CHOSEN for ambient auras (no R3F cost on every page).
- **liquid-logo** (paper-design) — an app, not a lib; GLSL liquid-metal
  technique. → F-mark gets shaders-react effect if a metal/liquid export
  exists, else SVG + animated gradient + turbulence displacement
  (zero-dep fallback).
- **liquid-glass-js** (dashersw) — WebGL refraction glass; NOT on npm,
  html2canvas-based, no React wrapper. → reference only; glass surfaces
  are CSS `backdrop-filter` (blur+saturate), gradient hairline borders,
  noise overlay, inner highlight.
- **R3F matrix for React 18 / Next 14.2**: `@react-three/fiber@8.18.0` +
  `@react-three/drei@9.122.0` + `three@0.170.x` (fiber9/drei10 need
  React 19 — do not upgrade). R3F used ONLY for the Cash Terrain
  (dynamic import, `ssr: false`, WebGL + reduced-motion fallback to 2D).
- **cmdk 1.1.1** for the palette.

## Token sketch (finalized in P1 with ui-ux-design/dataviz skills)
- Base layers: deep ink `#07090F` → `#0B0E17` → raised `#121627`
- Glass: white α3–6% fills · 1px white α8–12% hairline · blur 16–24px ·
  saturate 1.4 · noise texture overlay · inner top highlight
- Accent: **keep FinDesk amber** (#E8730A family, recalibrated for dark)
  — brand continuity; aura spectrum: violet/teal/amber mesh gradients
- Status: mint (ok) · amber (warn) · claret (danger), AA on glass
- Type: display **Space Grotesk** · text **Inter** · data **JetBrains
  Mono** (via next/font, self-hosted) — confirm pairing in P1
- Money stays `formatINR`, IST at the edge, headings keep their text so
  the Playwright smoke suite stays green

## Hard constraints carried over
- No client-side money math (sandbox = backend `/forecast/whatif`)
- Contract-first for any new endpoint; regen `shared/`
- WCAG 2.1 AA on signature surfaces (contrast ON glass, not behind it)
- Every phase: commit + push + session-log checkpoint (autonomous-run
  protocol; user may be away)
