"use client";

import {
  parseEventPage,
  parseRunEvent,
  parseRunWorkspace,
  type RunEvent,
  type RunWorkspace,
} from "@autobots/api-client";
import {
  CircleAlert,
  CircleCheck,
  CircleDashed,
  FileText,
  ScanSearch,
  TriangleAlert,
} from "lucide-react";
import Link from "next/link";
import {
  useEffect,
  useState,
  type ComponentProps,
  type ReactNode,
} from "react";

import { ContinueRun } from "@/components/continue-run";
import { RunControls } from "@/components/run-controls";
import { ToolsUsed } from "@/components/tool-uses";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { UnknownEffects } from "@/components/unknown-effects";
import { cn } from "@/lib/utils";

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
// Decision 0021: the header's short state words, as the run list says them, in a tone that repeats them.
const STATUS_LABEL: Record<string, string> = {
  queued: "Queued",
  running: "Running",
  waiting_input: "Waiting for input",
  waiting_approval: "Waiting for approval",
  paused: "Paused",
  verifying: "Verifying",
  cancelling: "Cancelling",
  succeeded: "Succeeded",
  failed: "Failed",
  cancelled: "Cancelled",
};
const STATUS_TONE: Record<string, ComponentProps<typeof Badge>["variant"]> = {
  queued: "muted",
  running: "live",
  waiting_input: "attention",
  waiting_approval: "attention",
  paused: "outline",
  verifying: "live",
  cancelling: "muted",
  succeeded: "success",
  failed: "danger",
  cancelled: "muted",
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
  if (payload.type === "tool.use.started") {
    return `Tool ${payload.tool_id} started`;
  }
  if (payload.type === "tool.use.completed") {
    return `Tool ${payload.tool_id} ${payload.outcome}${payload.code ? ` (${payload.code})` : ""}`;
  }
  return payload.type === "artifact.published"
    ? `Artifact ${payload.name} published`
    : `Artifact ${payload.name} is missing`;
}

// Decision 0017 Q13: an event type this page doesn't know is skipped, never an error.
function known(raw: unknown): RunEvent | null {
  try {
    return parseRunEvent(raw);
  } catch {
    return null;
  }
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
        const event = known(JSON.parse(message.data as string));
        if (event === null || event.sequence <= cursor) return;
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
        const raw = (await reply.json()) as { events?: unknown[] };
        const page = parseEventPage({ ...raw, events: [] });
        if (closed) return;
        if (page.gap) setGap(true);
        add(
          (raw.events ?? [])
            .map(known)
            .filter((event): event is RunEvent => event !== null),
        );
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
      <div className="mx-auto max-w-6xl space-y-4">
        <PageHeader title="Run" />
        <p role="alert" data-state="unavailable" className="text-sm">
          That run is not available. Sign in with access to it, or check the
          link.
        </p>
      </div>
    );
  }
  if (snapshot === null) {
    return (
      <div className="mx-auto max-w-6xl space-y-4">
        <PageHeader title="Run" />
        <p role="status" data-state="loading" className="text-sm">
          {connection === "reconnecting"
            ? CONNECTION_TEXT.reconnecting
            : "Loading this run."}
        </p>
      </div>
    );
  }
  const timeline = [...events.values()].sort((a, b) => a.sequence - b.sequence);
  const label = STATUS_LABEL[snapshot.run.status];
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex min-w-0 flex-wrap items-center gap-3">
          <h1 className="text-[32px] leading-tight">Run</h1>
          {label === undefined ? null : (
            // The status sentence below says the same to assistive technology.
            <Badge
              aria-hidden="true"
              variant={STATUS_TONE[snapshot.run.status] ?? "outline"}
              dot
            >
              {label}
            </Badge>
          )}
        </div>
        <p className="text-sm">
          <Link
            href={`/runs/${runId}/inspector`}
            className={buttonVariants({ variant: "outline", size: "sm" })}
          >
            <ScanSearch aria-hidden="true" />
            Inspect this run
          </Link>
        </p>
      </header>
      <div className="grid gap-x-10 xl:grid-cols-[minmax(0,1fr)_18rem]">
        <div className="min-w-0 space-y-6">
          <Section id="status-heading" title="Status">
            <p
              role="status"
              data-run-status={snapshot.run.status}
              className="text-[15px] leading-relaxed"
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
                <Link
                  href="/approvals"
                  className="text-attention font-medium underline underline-offset-4"
                >
                  Review it in Approvals
                </Link>
              </p>
            ) : null}
            <p
              data-connection={connection}
              className="text-muted-foreground flex items-center gap-2 text-xs"
            >
              <span
                aria-hidden="true"
                className={cn(
                  "size-1.5 shrink-0 rounded-full",
                  connection === "live"
                    ? "bg-live-text"
                    : "bg-muted-foreground",
                )}
              />
              {CONNECTION_TEXT[connection]}
            </p>
            {snapshot.can_continue ? <ContinueRun runId={runId} /> : null}
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
          </Section>
          {snapshot.verification === null ? null : (
            <Section id="verification-heading" title="Verification">
              {snapshot.verification.passed ? (
                <p
                  data-verification="passed"
                  className="flex items-start gap-2.5 text-sm leading-relaxed"
                >
                  <CircleCheck
                    aria-hidden="true"
                    className="text-success-text mt-0.5 size-4 shrink-0"
                  />
                  {snapshot.verification.checks === 0
                    ? "An artifact was published. No content check was defined for this goal, so its content wasn't judged."
                    : "Every required artifact and check passed."}
                </p>
              ) : (
                <div
                  data-verification="failed"
                  className="flex items-start gap-2.5 text-sm leading-relaxed"
                >
                  <CircleAlert
                    aria-hidden="true"
                    className="text-destructive mt-0.5 size-4 shrink-0"
                  />
                  <div className="min-w-0 space-y-1">
                    <p>Not everything required was met:</p>
                    <ul className="marker:text-muted-foreground list-disc pl-5">
                      {snapshot.verification.unmet.map((item) => (
                        <li key={item} className="break-words">
                          {item.replaceAll("_", " ").replace(":", ": ")}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}
            </Section>
          )}
          <Section id="goal-heading" title="Goal">
            <p className="font-serif text-[17px] leading-relaxed break-words">
              {snapshot.objective ?? "No goal is recorded."}
            </p>
            {snapshot.criteria.length === 0 ? null : (
              <ul className="marker:text-muted-foreground list-disc space-y-1 pl-5 text-sm leading-relaxed">
                {snapshot.criteria.map((criterion) => (
                  <li key={criterion.id} className="break-words">
                    {criterion.text}
                  </li>
                ))}
              </ul>
            )}
          </Section>
          <Section id="plan-heading" title="Plan">
            {snapshot.plan === null ? (
              <p className="text-muted-foreground text-sm">No plan yet.</p>
            ) : (
              <>
                <p className="text-muted-foreground text-xs">
                  Version {snapshot.plan.version}
                  {snapshot.plan.revision_reason === null
                    ? ""
                    : `, revised because: ${snapshot.plan.revision_reason}`}
                </p>
                <ul className="bg-card divide-y rounded-xl border text-sm">
                  {snapshot.plan.tasks.map((task) => (
                    <li
                      key={task.id}
                      data-task-status={task.status}
                      className="flex items-start gap-3 px-4 py-3"
                    >
                      {task.status === "complete" ? (
                        <CircleCheck
                          aria-hidden="true"
                          className="text-success-text mt-0.5 size-4 shrink-0"
                        />
                      ) : (
                        <CircleDashed
                          aria-hidden="true"
                          className="text-muted-foreground mt-0.5 size-4 shrink-0"
                        />
                      )}
                      <span className="min-w-0 leading-relaxed break-words">
                        <span className="font-medium">{task.title}</span>:{" "}
                        <span className="text-muted-foreground">
                          {task.status === "complete" ? "complete" : "open"}
                          {task.evidence_summary === null
                            ? ""
                            : `. ${task.evidence_summary}`}
                        </span>
                      </span>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </Section>
          <ToolsUsed
            runId={runId}
            version={
              [...events.values()].filter((event) =>
                event.payload.type.startsWith("tool.use."),
              ).length
            }
          />
          {snapshot.unknown_operations.length === 0 ? null : (
            <section
              aria-labelledby="unknown-heading"
              className="border-attention/40 bg-card dark:bg-attention/5 space-y-3 rounded-xl border p-5"
            >
              <h2
                id="unknown-heading"
                className="flex items-center gap-2 text-sm font-semibold"
              >
                <TriangleAlert
                  aria-hidden="true"
                  className="text-attention size-4 shrink-0"
                />
                Unknown outcomes
              </h2>
              <UnknownEffects
                runId={runId}
                operations={snapshot.unknown_operations}
                onResolved={() => setRefreshes((count) => count + 1)}
              />
            </section>
          )}
          {snapshot.run.parent_run_id === null ? null : (
            <p
              data-field="parent-run"
              className="text-muted-foreground border-t pt-6 text-sm"
            >
              This run is a part of{" "}
              <a
                href={`/runs/${snapshot.run.parent_run_id}`}
                className="text-foreground font-medium underline underline-offset-4"
              >
                its parent run
              </a>
              .
            </p>
          )}
          {snapshot.assignments.length === 0 ? null : (
            <Section id="assignments-heading" title="Assignments">
              <ul className="divide-y text-sm">
                {snapshot.assignments.map((assignment) => (
                  <li
                    key={assignment.id}
                    data-assignment={assignment.status}
                    className="py-2 first:pt-0 last:pb-0"
                  >
                    <a
                      href={`/runs/${assignment.child_run_id}`}
                      className="font-medium underline underline-offset-4"
                    >
                      {assignment.expert}
                    </a>
                    <span className="text-muted-foreground">
                      : {assignment.outcome ?? assignment.status}
                    </span>
                  </li>
                ))}
              </ul>
            </Section>
          )}
          <Section id="artifacts-heading" title="Artifacts">
            {snapshot.artifacts.length === 0 ? (
              <p className="text-muted-foreground text-sm">No artifacts yet.</p>
            ) : (
              <ul className="divide-y text-sm">
                {snapshot.artifacts.map((artifact) => (
                  <li
                    key={artifact.id}
                    data-artifact-status={artifact.status}
                    className="flex items-start gap-2.5 py-2 first:pt-0 last:pb-0"
                  >
                    <FileText
                      aria-hidden="true"
                      className="text-muted-foreground mt-0.5 size-4 shrink-0"
                    />
                    <span className="min-w-0 break-words">
                      {artifact.status === "published" ? (
                        <a
                          href={`/api/v1/artifacts/${artifact.id}/download`}
                          className="font-mono text-[13px] font-medium underline underline-offset-4"
                        >
                          {artifact.name}
                        </a>
                      ) : (
                        <span className="font-mono text-[13px]">
                          {`${artifact.name}: missing`}
                        </span>
                      )}{" "}
                      <span className="text-muted-foreground font-mono text-xs break-all">
                        {artifact.size_bytes} bytes, sha256{" "}
                        {artifact.sha256.slice(0, 12)}
                      </span>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Section>
          <Section id="timeline-heading" title="Timeline">
            {gap ? (
              <p data-gap="true" className="text-sm">
                Earlier activity is no longer retained, so this starts later.
                The status above is current.
              </p>
            ) : null}
            <ol className="space-y-2 border-l pl-4 text-sm">
              {timeline.map((event) => (
                <li
                  key={event.sequence}
                  data-sequence={event.sequence}
                  className="relative break-words"
                >
                  <span
                    aria-hidden="true"
                    className="bg-muted-foreground absolute top-2 -left-[19.5px] size-1.5 rounded-full"
                  />
                  {describe(event)}
                </li>
              ))}
            </ol>
          </Section>
        </div>
        <div className="min-w-0 space-y-6 pt-6 xl:pt-0">
          {snapshot.expert === null ? null : (
            <Section id="expert-heading" title="Expert">
              <div
                data-expert={snapshot.expert.name}
                className="space-y-1.5 text-sm"
              >
                <p className="break-words">
                  {snapshot.expert.name}, version {snapshot.expert.version}
                </p>
                <p className="text-muted-foreground break-words">
                  Tools:{" "}
                  <span className="font-mono text-xs">
                    {snapshot.expert.tools.length === 0
                      ? "none"
                      : snapshot.expert.tools.join(", ")}
                  </span>
                </p>
                <p className="text-muted-foreground break-words">
                  Models:{" "}
                  {Object.keys(snapshot.expert.role_bindings).length === 0
                    ? "the workspace setting"
                    : Object.entries(snapshot.expert.role_bindings)
                        .map(([role, profile]) => `${role}: ${profile}`)
                        .join(", ")}
                </p>
              </div>
            </Section>
          )}
          <Section id="models-heading" title="Models">
            {snapshot.role_map.length === 0 ? (
              <p className="text-muted-foreground text-sm">
                This run has no frozen role map.
              </p>
            ) : (
              <div data-field="role-map" className="space-y-2.5 text-sm">
                <p className="text-muted-foreground text-[13px] leading-relaxed">
                  What this run froze when it was admitted. Only the
                  executor&apos;s binding dispatches in this release, and other
                  roles that differ from it don&apos;t take effect.
                </p>
                {snapshot.role_map.find(
                  (binding) => binding.role === "summarizer",
                )?.profile !==
                snapshot.role_map.find((binding) => binding.role === "executor")
                  ?.profile ? (
                  <p
                    data-role-map="summarizer"
                    className="text-[13px] leading-relaxed"
                  >
                    The summarizer differs here, so this run pauses with
                    route_not_bound if it needs compaction, and resuming
                    won&apos;t clear that.
                  </p>
                ) : null}
                <ul className="space-y-1.5">
                  {snapshot.role_map.map((binding) => (
                    <li
                      key={binding.role}
                      className="text-[13px] leading-snug break-words"
                    >
                      {binding.role}:{" "}
                      <span className="font-mono text-xs break-all">
                        {binding.canonical_id}
                      </span>
                      <span className="text-muted-foreground">
                        , requested as{" "}
                      </span>
                      <span className="text-muted-foreground font-mono text-xs break-all">
                        {binding.wire_id}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </Section>
          <Section id="budgets-heading" title="Budgets">
            <div
              data-field="budgets"
              className="space-y-2 text-[13px] leading-relaxed tabular-nums"
            >
              <p>
                Tokens: up to {snapshot.budgets.max_output_tokens_per_call}{" "}
                output tokens per call, and about{" "}
                {Math.round(snapshot.budgets.context_tokens / 1000)}K tokens of
                context. Used so far: {snapshot.usage.input_tokens} in,{" "}
                {snapshot.usage.output_tokens} out.
              </p>
              <p>
                Spend limit: US$
                {(snapshot.run.budget.limit_micro_usd / 1_000_000).toFixed(2)}.
                Reported so far: US$
                {snapshot.run.budget.spent_micro_usd / 1_000_000}. Held as an
                estimate for calls not settled: US$
                {snapshot.run.budget.reserved_micro_usd / 1_000_000}.{" "}
                <span className="text-muted-foreground">
                  The workspace&apos;s per-run and daily limits apply too, and
                  the lowest one stops the run.
                </span>
              </p>
            </div>
          </Section>
          <Section id="usage-heading" title="Usage">
            <p className="text-[13px] leading-relaxed tabular-nums">
              {snapshot.usage.model_calls} model calls,{" "}
              {snapshot.usage.tool_dispatches} tool calls,{" "}
              {snapshot.usage.repairs} repairs. Spent $
              {snapshot.run.budget.spent_micro_usd / 1_000_000} of $
              {snapshot.run.budget.limit_micro_usd / 1_000_000}, with $
              {snapshot.run.budget.reserved_micro_usd / 1_000_000} reserved.
            </p>
            {snapshot.outstanding.uncertain_calls +
              snapshot.outstanding.unknown_effects +
              snapshot.outstanding.unreported_charges ===
            0 ? null : (
              <p
                data-outstanding="true"
                className="text-[13px] leading-relaxed tabular-nums"
              >
                Not settled: {snapshot.outstanding.uncertain_calls} model calls
                with unknown outcomes, {snapshot.outstanding.unknown_effects}{" "}
                tool effects with unknown outcomes,{" "}
                {snapshot.outstanding.unreported_charges} calls with no reported
                charge.
              </p>
            )}
          </Section>
        </div>
      </div>
    </div>
  );
}

// Decision 0021: a hairline-separated section in place of a card. Its heading names the region.
function Section({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <section aria-labelledby={id} className="space-y-3 border-t pt-6">
      <h2 id={id} className="text-sm font-semibold">
        {title}
      </h2>
      {children}
    </section>
  );
}
