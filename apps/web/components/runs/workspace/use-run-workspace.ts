/**
 * The run page's state from React: `lib/run-connection.ts` reads the snapshot, replays and follows
 * the stream, and this hook gives it the browser's EventSource, timers and stream preference
 * (WRUN-02, WRUN-04). Leaving the page closes the stream and aborts its reads, and nothing else: a
 * run's work belongs to its worker (PRD-Development-Harness DH-06).
 */
import { useCallback, useEffect, useRef, useState } from "react";

import {
  EMPTY_VIEW,
  FRAME_TYPES,
  RunConnection,
  type RunView,
  type Stream,
  type StreamHandlers,
} from "@/lib/run-connection";

export interface RunWorkspaceState extends RunView {
  /** Reads the snapshot again, in turn with the stream's refreshes, such as after a page action. */
  refresh: () => void;
  /** Tries again now rather than after the current wait. */
  retry: () => void;
}

function openStream(url: string, on: StreamHandlers): Stream {
  const source = new EventSource(url);
  source.onopen = () => on.open();
  source.onerror = () => on.error();
  for (const type of FRAME_TYPES) {
    source.addEventListener(type, (message) => on.frame(type, message.data));
  }
  return source;
}

function later(run: () => void, ms: number): () => void {
  const timer = setTimeout(run, ms);
  return () => clearTimeout(timer);
}

// US-15.24, PRD-Studio SE-03: "Stream text as it's written", on unless turned off in this browser.
// The Appearance control and the before-paint script both set this root attribute.
function streamWanted(): boolean {
  return document.documentElement.dataset.stream !== "off";
}

function report(record: { event: string; name: string }): void {
  console.error("Reading this run failed unexpectedly.", record);
}

export function useRunWorkspace(runId: string): RunWorkspaceState {
  // Tagged with its run, so another run's page never starts from this one's state.
  const [shown, setShown] = useState<{ runId: string; view: RunView } | null>(
    null,
  );
  const connection = useRef<RunConnection | null>(null);

  useEffect(() => {
    const opened = new RunConnection({
      runId,
      open: openStream,
      later,
      streamWanted,
      report,
      onChange: (view) => setShown({ runId, view }),
    });
    connection.current = opened;
    opened.start();
    return () => {
      opened.close();
      if (connection.current === opened) connection.current = null;
    };
  }, [runId]);

  const refresh = useCallback(() => {
    connection.current?.refresh();
  }, []);
  const retry = useCallback(() => {
    connection.current?.retry();
  }, []);
  const view =
    shown !== null && shown.runId === runId ? shown.view : EMPTY_VIEW;
  return { ...view, refresh, retry };
}
