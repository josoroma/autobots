"use client";

import {
  parseEventPage,
  parseRunEvent,
  parseRunWorkspace,
  type RunEvent,
  type RunWorkspace,
} from "@autobots/api-client";
import Link from "next/link";
import { useEffect, useState } from "react";

import { RunControls } from "@/components/run-controls";
import { Card } from "@/components/ui/card";
import { UnknownEffects } from "@/components/unknown-effects";

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
  if (payload.type === "effect.reconciled") {
    return `An unknown effect was reconciled: ${payload.outcome.replaceAll("_", " ")}`;
  }
  if (payload.type === "approval.requested") {
    return `Approval requested for ${payload.tool_id}`;
  }
  if (payload.type === "approval.decided") {
    return `Approval ${payload.decision}`;
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
  const [refreshes, setRefreshes] = useState(0);

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

  // After a page's own action, without waiting for the next event.
  useEffect(() => {
    if (refreshes === 0) return;
    let active = true;
    fetch(`/api/v1/runs/${encodeURIComponent(runId)}/workspace`, {
      cache: "no-store",
    })
      .then(async (reply) => {
        if (active && reply.ok)
          setSnapshot(parseRunWorkspace(await reply.json()));
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [refreshes, runId]);

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
        {snapshot.run.status === "waiting_approval" ? (
          <p className="text-sm">
            <Link href="/approvals" className="font-medium underline">
              Review it in Approvals
            </Link>
          </p>
        ) : null}
        <p
          data-connection={connection}
          className="text-muted-foreground text-sm"
        >
          {CONNECTION_TEXT[connection]}
        </p>
        <RunControls
          runId={runId}
          status={snapshot.run.status}
          version={snapshot.run.version}
          openCalls={
            snapshot.outstanding.uncertain_calls +
            snapshot.outstanding.unreported_charges
          }
          onChanged={() => setRefreshes((count) => count + 1)}
        />
      </Card>
      {snapshot.verification === null ? null : (
        <Card aria-labelledby="verification-heading" className="space-y-2">
          <h2 id="verification-heading" className="text-lg font-medium">
            Verification
          </h2>
          {snapshot.verification.passed ? (
            <p data-verification="passed" className="text-sm">
              {snapshot.verification.checks === 0
                ? "An artifact was published. No content check was defined for this goal, so its content wasn't judged."
                : "Every required artifact and check passed."}
            </p>
          ) : (
            <div data-verification="failed" className="space-y-1 text-sm">
              <p>Not everything required was met:</p>
              <ul className="list-disc pl-5">
                {snapshot.verification.unmet.map((item) => (
                  <li key={item}>
                    {item.replaceAll("_", " ").replace(":", ": ")}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>
      )}
      {snapshot.expert === null ? null : (
        <Card aria-labelledby="expert-heading" className="space-y-2">
          <h2 id="expert-heading" className="text-lg font-medium">
            Expert
          </h2>
          <div data-expert={snapshot.expert.name} className="space-y-1 text-sm">
            <p>
              {snapshot.expert.name}, version {snapshot.expert.version}
            </p>
            <p>
              Tools:{" "}
              {snapshot.expert.tools.length === 0
                ? "none"
                : snapshot.expert.tools.join(", ")}
            </p>
            <p>
              Models:{" "}
              {Object.keys(snapshot.expert.role_bindings).length === 0
                ? "the workspace setting"
                : Object.entries(snapshot.expert.role_bindings)
                    .map(([role, profile]) => `${role}: ${profile}`)
                    .join(", ")}
            </p>
          </div>
        </Card>
      )}
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
      {snapshot.unknown_operations.length === 0 ? null : (
        <Card aria-labelledby="unknown-heading" className="space-y-2">
          <h2 id="unknown-heading" className="text-lg font-medium">
            Unknown outcomes
          </h2>
          <UnknownEffects
            runId={runId}
            operations={snapshot.unknown_operations}
            onResolved={() => setRefreshes((count) => count + 1)}
          />
        </Card>
      )}
      {snapshot.assignments.length === 0 ? null : (
        <Card aria-labelledby="assignments-heading" className="space-y-2">
          <h2 id="assignments-heading" className="text-lg font-medium">
            Assignments
          </h2>
          <ul className="space-y-1 text-sm">
            {snapshot.assignments.map((assignment) => (
              <li key={assignment.id} data-assignment={assignment.status}>
                <a
                  href={`/runs/${assignment.child_run_id}`}
                  className="font-medium underline"
                >
                  {assignment.expert}
                </a>
                : {assignment.outcome ?? assignment.status}
              </li>
            ))}
          </ul>
        </Card>
      )}
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
          repairs. Spent ${snapshot.run.budget.spent_micro_usd / 1_000_000} of $
          {snapshot.run.budget.limit_micro_usd / 1_000_000}, with $
          {snapshot.run.budget.reserved_micro_usd / 1_000_000} reserved.
        </p>
        {snapshot.outstanding.uncertain_calls +
          snapshot.outstanding.unknown_effects +
          snapshot.outstanding.unreported_charges ===
        0 ? null : (
          <p data-outstanding="true" className="text-sm">
            Not settled: {snapshot.outstanding.uncertain_calls} model calls with
            unknown outcomes, {snapshot.outstanding.unknown_effects} tool
            effects with unknown outcomes,{" "}
            {snapshot.outstanding.unreported_charges} calls with no reported
            charge.
          </p>
        )}
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
