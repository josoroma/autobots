"use client";

import {
  parseEventPage,
  parseRunEvent,
  parseRunWorkspace,
  type RunEvent,
  type RunWorkspace,
} from "@autobots/api-client";
import { useEffect, useState } from "react";

import { Card } from "@/components/ui/card";

// Reasons are kept apart from status, so "paused" and "failed" can say why.
const STATUS_TEXT: Record<string, string> = {
  queued: "Queued. Waiting for a worker.",
  running: "Running.",
  waiting_input: "Waiting for your input.",
  waiting_approval: "Waiting for an approval decision.",
  paused: "Paused. No new work starts until it resumes.",
  verifying: "Checking the result against its criteria.",
  cancelling: "Cancelling. Active work is being settled.",
  succeeded: "Succeeded.",
  failed: "Failed.",
  cancelled: "Cancelled.",
};
const CONNECTION_TEXT = {
  loading: "Loading",
  live: "Live",
  reconnecting: "Reconnecting. Showing the last known state.",
  ended: "Finished. No more activity is expected.",
} as const;
type Connection = keyof typeof CONNECTION_TEXT;
const RECONNECT_MS = 1000;

function describe(event: RunEvent): string {
  const payload = event.payload;
  if (payload.type === "run.status_changed") {
    return payload.previous === payload.current
      ? `Run ${payload.current}`
      : `Run moved from ${payload.previous} to ${payload.current}`;
  }
  return payload.type === "artifact.published"
    ? `Artifact ${payload.name} published`
    : `Artifact ${payload.name} is missing`;
}

export function RunWorkspaceView({ runId }: { runId: string }) {
  const [snapshot, setSnapshot] = useState<RunWorkspace | null>(null);
  const [events, setEvents] = useState<ReadonlyMap<number, RunEvent>>(
    () => new Map(),
  );
  const [connection, setConnection] = useState<Connection>("loading");
  const [unavailable, setUnavailable] = useState(false);
  const [gap, setGap] = useState(false);

  useEffect(() => {
    let closed = false;
    let source: EventSource | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let cursor = 0;
    const base = `/api/v1/runs/${encodeURIComponent(runId)}`;

    const add = (incoming: readonly RunEvent[]): void => {
      setEvents((current) => {
        const next = new Map(current);
        for (const event of incoming) next.set(event.sequence, event);
        return next;
      });
    };

    const refresh = async (): Promise<boolean> => {
      const reply = await fetch(`${base}/workspace`, {
        cache: "no-store",
      }).catch(() => null);
      if (closed) return false;
      if (reply?.ok !== true) {
        if (reply?.status === 404 || reply?.status === 401) {
          setUnavailable(true);
        }
        return false;
      }
      setSnapshot(parseRunWorkspace(await reply.json()));
      return true;
    };

    const retry = (): void => {
      setConnection("reconnecting");
      timer = setTimeout(() => void start(), RECONNECT_MS);
    };

    const connect = (): void => {
      source = new EventSource(`${base}/events/stream?after=${cursor}`);
      source.onopen = () => setConnection("live");
      source.addEventListener("run", (message) => {
        const event = parseRunEvent(JSON.parse(message.data as string));
        if (event.sequence <= cursor) return;
        add([event]);
        void refresh();
      });
      source.addEventListener("cursor", (message) => {
        cursor = Math.max(
          cursor,
          (JSON.parse(message.data as string) as { cursor: number }).cursor,
        );
      });
      source.addEventListener("gap", () => {
        setGap(true);
        void refresh();
      });
      source.addEventListener("end", () => {
        source?.close();
        setConnection("ended");
      });
      source.onerror = () => {
        // The browser's own retry would resume from a stale URL, so this uses the current cursor.
        source?.close();
        if (!closed) retry();
      };
    };

    // Replays everything after the cursor, so nothing missed while disconnected stays missing.
    const start = async (): Promise<void> => {
      const loaded = await refresh();
      if (closed) return;
      if (!loaded) {
        retry();
        return;
      }
      for (;;) {
        const reply = await fetch(`${base}/events?after=${cursor}`, {
          cache: "no-store",
        }).catch(() => null);
        if (closed) return;
        if (reply?.ok !== true) {
          retry();
          return;
        }
        const page = parseEventPage(await reply.json());
        if (closed) return;
        if (page.gap) setGap(true);
        add(page.events);
        if (page.next_cursor === cursor) break;
        cursor = page.next_cursor;
      }
      connect();
    };

    void start();
    return () => {
      closed = true;
      clearTimeout(timer);
      source?.close();
    };
  }, [runId]);

  if (unavailable) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Run</h1>
        <p role="alert" data-state="unavailable" className="text-sm">
          That run is not available. Sign in with access to it, or check the
          link.
        </p>
      </div>
    );
  }
  if (snapshot === null) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Run</h1>
        <p role="status" data-state="loading" className="text-sm">
          {connection === "reconnecting"
            ? CONNECTION_TEXT.reconnecting
            : "Loading this run."}
        </p>
      </div>
    );
  }
  const timeline = [...events.values()].sort((a, b) => a.sequence - b.sequence);
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Run</h1>
      <Card aria-labelledby="status-heading" className="space-y-2">
        <h2 id="status-heading" className="text-lg font-medium">
          Status
        </h2>
        <p
          role="status"
          data-run-status={snapshot.run.status}
          className="text-sm"
        >
          {STATUS_TEXT[snapshot.run.status]}
          {snapshot.stop_reason === null ? null : (
            <span data-stop-reason={snapshot.stop_reason}>
              {" "}
              Reason: {snapshot.stop_reason.replaceAll("_", " ")}.
            </span>
          )}
        </p>
        <p
          data-connection={connection}
          className="text-muted-foreground text-sm"
        >
          {CONNECTION_TEXT[connection]}
        </p>
      </Card>
      <Card aria-labelledby="goal-heading" className="space-y-2">
        <h2 id="goal-heading" className="text-lg font-medium">
          Goal
        </h2>
        <p className="text-sm">
          {snapshot.objective ?? "No goal is recorded."}
        </p>
        {snapshot.criteria.length === 0 ? null : (
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {snapshot.criteria.map((criterion) => (
              <li key={criterion.id}>{criterion.text}</li>
            ))}
          </ul>
        )}
      </Card>
      <Card aria-labelledby="plan-heading" className="space-y-2">
        <h2 id="plan-heading" className="text-lg font-medium">
          Plan
        </h2>
        {snapshot.plan === null ? (
          <p className="text-sm">No plan yet.</p>
        ) : (
          <>
            <p className="text-sm">
              Version {snapshot.plan.version}
              {snapshot.plan.revision_reason === null
                ? ""
                : `, revised because: ${snapshot.plan.revision_reason}`}
            </p>
            <ul className="space-y-1 text-sm">
              {snapshot.plan.tasks.map((task) => (
                <li key={task.id} data-task-status={task.status}>
                  {task.title}:{" "}
                  {task.status === "complete" ? "complete" : "open"}
                  {task.evidence_summary === null
                    ? ""
                    : `. ${task.evidence_summary}`}
                </li>
              ))}
            </ul>
          </>
        )}
      </Card>
      <Card aria-labelledby="artifacts-heading" className="space-y-2">
        <h2 id="artifacts-heading" className="text-lg font-medium">
          Artifacts
        </h2>
        {snapshot.artifacts.length === 0 ? (
          <p className="text-sm">No artifacts yet.</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {snapshot.artifacts.map((artifact) => (
              <li key={artifact.id} data-artifact-status={artifact.status}>
                {artifact.status === "published" ? (
                  <a
                    href={`/api/v1/artifacts/${artifact.id}/download`}
                    className="font-medium underline"
                  >
                    {artifact.name}
                  </a>
                ) : (
                  `${artifact.name}: missing`
                )}{" "}
                <span className="text-muted-foreground">
                  {artifact.size_bytes} bytes, sha256{" "}
                  {artifact.sha256.slice(0, 12)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Card aria-labelledby="usage-heading" className="space-y-2">
        <h2 id="usage-heading" className="text-lg font-medium">
          Usage
        </h2>
        <p className="text-sm">
          {snapshot.usage.model_calls} model calls,{" "}
          {snapshot.usage.tool_dispatches} tool calls, {snapshot.usage.repairs}{" "}
          repairs. Spent {snapshot.run.budget.spent_micro_usd / 1_000_000} of $
          {snapshot.run.budget.limit_micro_usd / 1_000_000}.
        </p>
      </Card>
      <Card aria-labelledby="timeline-heading" className="space-y-2">
        <h2 id="timeline-heading" className="text-lg font-medium">
          Timeline
        </h2>
        {gap ? (
          <p data-gap="true" className="text-sm">
            Earlier activity is no longer retained, so this starts later. The
            status above is current.
          </p>
        ) : null}
        <ol className="space-y-1 text-sm">
          {timeline.map((event) => (
            <li key={event.sequence} data-sequence={event.sequence}>
              {describe(event)}
            </li>
          ))}
        </ol>
      </Card>
    </div>
  );
}
