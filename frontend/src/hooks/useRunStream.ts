"use client";
// Live agent-run events over SSE. fetch-based (EventSource can't send the
// Authorization header). Event shapes: contracts/events.md.
import { useEffect, useRef, useState } from "react";

import { api, getToken } from "@/lib/api";

export type RunEvent = {
  event: string;
  step_id?: string;
  name?: string;
  status?: string;
  summary?: string;
  [k: string]: unknown;
};

export function useRunStream(runId: string | null) {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [done, setDone] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!runId) return;
    setEvents([]);
    setDone(false);
    const controller = new AbortController();
    abortRef.current = controller;

    (async () => {
      try {
        const res = await fetch(api.streamPath(runId), {
          headers: { Authorization: `Bearer ${getToken()}` },
          signal: controller.signal,
        });
        if (!res.ok || !res.body) throw new Error(`stream ${res.status}`);
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
            if (evt.event?.startsWith("run.done@")) setDone(true);
          }
        }
      } catch (err) {
        if (!(err instanceof DOMException && err.name === "AbortError")) {
          setEvents((prev) => [...prev, { event: "stream.error", summary: String(err) }]);
        }
      } finally {
        setDone(true);
      }
    })();

    return () => controller.abort();
  }, [runId]);

  return { events, done };
}
