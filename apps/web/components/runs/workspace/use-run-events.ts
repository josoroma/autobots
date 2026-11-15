/**
 * What the run page derives from its stored events: the timeline, the tool-event count that tells
 * Tools used to read again, and the newest published result. `RunConnection` keeps one map until an
 * event arrives, so live text, which changes often, never sorts or filters the events again
 * (WRUN-01). Replay, the stream, backoff and deduplication stay in `lib/runs/connection.ts`, behind
 * `useRunWorkspace`.
 */
import type { RunEvent } from "@autobots/api-client";
import { useMemo } from "react";

import {
  latestPublished,
  toolEventCount,
  toTimeline,
} from "@/lib/runs/run-events";

export interface RunEvents {
  /** Stored events, oldest first. */
  timeline: readonly RunEvent[];
  /** Changes exactly when a tool-use event arrives. */
  toolEvents: number;
  /** The newest published artifact, the run's stored result. */
  published: { id: string; name: string } | null;
}

export function useRunEvents(events: ReadonlyMap<number, RunEvent>): RunEvents {
  return useMemo(
    () => ({
      timeline: toTimeline(events.values()),
      toolEvents: toolEventCount(events.values()),
      published: latestPublished(events.values()),
    }),
    [events],
  );
}
