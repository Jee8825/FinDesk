// Client-side decay math, mirroring recall/core/decay.py, for the curve viz.

export const LAMBDAS: Record<string, number> = {
  episodic: 0.35,
  semantic: 0.02,
  procedural: 0.001,
};

export function strengthAt(
  s0: number,
  lambda: number,
  days: number
): number {
  return s0 * Math.exp(-lambda * days);
}

// Build a decay series over `days`, optionally reinforcing every `reinforceEvery`
// days (resets strength * r, capped at 1). Demonstrates retrieval reinforcement.
export function decaySeries(
  lambda: number,
  days: number,
  step = 1,
  reinforceEvery = 0,
  r = 1.25
): { day: number; strength: number; reinforced: number }[] {
  const out = [];
  let plainS0 = 1;
  let reinfS0 = 1;
  let reinfAnchor = 0;
  for (let d = 0; d <= days; d += step) {
    const plain = strengthAt(plainS0, lambda, d);
    let reinforced = strengthAt(reinfS0, lambda, d - reinfAnchor);
    if (reinforceEvery > 0 && d > 0 && d % reinforceEvery === 0) {
      reinforced = Math.min(1, reinforced * r);
      reinfS0 = reinforced;
      reinfAnchor = d;
    }
    out.push({ day: d, strength: round(plain), reinforced: round(reinforced) });
  }
  return out;
}

function round(x: number): number {
  return Math.round(x * 1000) / 1000;
}
