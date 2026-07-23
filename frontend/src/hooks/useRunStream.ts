"use client";
// Live agent-run events over SSE. fetch-based (EventSource can't send the
// Authorization header). Event shapes: contracts/events.md.
//
// Reliability contract (FE2): a dropped stream is NOT a finished run.
// - reconnects with capped exponential backoff; the server replays persisted
//   steps on every connect, so each (re)connect rebuilds `events` from scratch
//   and nothing is lost or duplicated;
// - `done` flips only on a real run.done@v1 — or, after the reconnect budget
//   is spent, when polling GET /agent/runs/{id} reports a terminal status;
// - `state` lets surfaces show "reconnecting…" instead of lying.
import { useEffect, useRef, useState } from "react";

import { api, authorizedFetch } from "@/lib/api";

export type RunEvent = {
  event: string;
  step_id?: string;
  name?: string;
  status?: string;
  summary?: string;
  [k: string]: unknown;
};

export type StreamState = "idle" | "connecting" | "live" | "reconnecting" | "polling" | "done";

const MAX_STREAM_ATTEMPTS = 6; // then fall back to status polling
const POLL_MS = 5_000;
const TERMINAL = new Set(["succeeded", "failed", "cancelled"]);

const backoffMs = (attempt: number) => Math.min(1_000 * 2 ** attempt, 10_000);

export function useRunStream(runId: string | null) {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [done, setDone] = useState(false);
  const [state, setState] = useState<StreamState>("idle");
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!runId) {
      setState("idle");
      return;
    }
    setEvents([]);
    setDone(false);
    setState("connecting");
    const controller = new AbortController();
    abortRef.current = controller;

    // abort-aware sleep so unmount never leaves a dangling timer
    const sleep = (ms: number) =>
      new Promise<void>((resolve) => {
        const t = setTimeout(resolve, ms);
        controller.signal.addEventListener(
          "abort",
          () => {
            clearTimeout(t);
            resolve();
          },
          { once: true },
        );
      });

    (async () => {
      let attempt = 0;
      let sawDone = false;

      while (!controller.signal.aborted && !sawDone && attempt <= MAX_STREAM_ATTEMPTS) {
        if (attempt > 0) {
          setState("reconnecting");
          await sleep(backoffMs(attempt - 1));
          if (controller.signal.aborted) return;
        }
        try {
          const res = await authorizedFetch(api.streamPath(runId), {
            signal: controller.signal,
          });
          if (!res.ok || !res.body) throw new Error(`stream ${res.status}`);
          // fresh connect: the server replays the persisted history first —
          // rebuild instead of appending so reconnects can't duplicate steps
          setEvents([]);
          setState("live");
          const reader = res.body.getReader();
          const decoder = new TextDecoder();
          let buffer = "";
          for (;;) {
            const { value, done: eof } = await reader.read();
            if (eof) break;
            buffer += decoder.decode(value, { stream: true });
            const frames = buffer.split("\n\n");
            buffer = frames.pop() ?? "";
            for (const frame of frames) {
              const data = frame
                .split("\n")
                .filter((l) => l.startsWith("data: "))
                .map((l) => l.slice(6))
                .join("\n");
              if (!data) continue;
              const evt = JSON.parse(data) as RunEvent;
              setEvents((prev) => [...prev, evt]);
              if (evt.event?.startsWith("run.done@")) sawDone = true;
            }
            if (sawDone) break;
          }
          if (sawDone) break;
          attempt += 1; // EOF without run.done = dropped mid-run
        } catch {
          if (controller.signal.aborted) return;
          attempt += 1;
        }
      }

      if (controller.signal.aborted) return;
      if (sawDone) {
        setDone(true);
        setState("done");
        return;
      }

      // Stream budget spent — the run may still be executing. Poll the
      // persisted run row until it goes terminal; steps self-heal from it.
      setState("polling");
      while (!controller.signal.aborted) {
        try {
          const run = await api.getRun(runId);
          setEvents(
            (run.steps ?? []).map((s) => ({
              event: "run.step@v1",
              step_id: s.step_id,
              name: s.name,
              status: s.status,
            })),
          );
          if (TERMINAL.has(run.status)) {
            setEvents((prev) => [...prev, { event: "run.done@v1", status: run.status }]);
            setDone(true);
            setState("done");
            return;
          }
        } catch {
          // backend unreachable — keep polling; authorizedFetch already
          // handled the 401-refresh path
        }
        await sleep(POLL_MS);
      }
    })();

    return () => controller.abort();
  }, [runId]);

  return { events, done, state };
}
