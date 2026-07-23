"use client";
// Start a graph run and invalidate queries when it actually finishes (FE1).
// Replaces the fire-and-hope `setTimeout(invalidate, 6000)` pattern: the run
// may take 2s or 40s — we follow the stream (with reconnect + poll fallback
// from useRunStream) and refetch exactly once, on run.done.
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

import { useRunStream, type StreamState } from "@/hooks/useRunStream";
import { api } from "@/lib/api";

export function useGraphRun(graph: string, invalidateKeys: string[][]) {
  const queryClient = useQueryClient();
  const [runId, setRunId] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const { events, done, state } = useRunStream(runId);
  const settled = useRef(false);

  const start = useCallback(async () => {
    if (runId && !done) return; // one run at a time per surface
    setStarting(true);
    settled.current = false;
    try {
      const run = await api.startRunByGraph(graph);
      setRunId(run.run_id);
    } finally {
      setStarting(false);
    }
  }, [graph, runId, done]);

  useEffect(() => {
    if (!done || !runId || settled.current) return;
    settled.current = true;
    for (const key of invalidateKeys) {
      void queryClient.invalidateQueries({ queryKey: key });
    }
    setRunId(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- invalidateKeys is a stable literal at call sites
  }, [done, runId, queryClient]);

  const lastStep = [...events].reverse().find((e) => e.event?.startsWith("run.step@"));
  const running = starting || (runId !== null && !done);

  return {
    start,
    running,
    stepName: running ? (lastStep?.name ?? null) : null,
    streamState: state as StreamState,
  };
}
