"use client";

import { parseRunWorkspace, type RunWorkspace } from "@autobots/api-client";
import { CircleAlert, Pause, Play, RotateCw } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { commandsFor } from "@/components/run-controls";
import { StateLine } from "@/components/run-list";
import { Button, buttonVariants } from "@/components/ui/button";
import { csrfFetch } from "@/lib/csrf-fetch";
import { cn } from "@/lib/utils";

type Command = "pause" | "resume" | "cancel";
type Task = NonNullable<RunWorkspace["plan"]>["tasks"][number];

const LABELS: Record<Command, string> = {
  pause: "Pause",
  resume: "Resume",
  cancel: "Cancel run",
};
const MARKER_TEXT: Record<Task["marker"], string> = {
  done: "Done",
  current: "Current",
  to_do: "To do",
};
const STALE =
  "This run changed after the panel loaded, so nothing was done. Reload the panel to see it now, then try again.";

function dollars(micro: number): string {
  return `US$${(micro / 1_000_000).toFixed(2)}`;
}

export function wallTime(seconds: number | null): string {
  if (seconds === null) return "—";
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const rest = seconds % 60;
  if (hours > 0) return `${hours}h ${String(minutes).padStart(2, "0")}m`;
  if (minutes > 0) return `${minutes}m ${String(rest).padStart(2, "0")}s`;
  return `${rest}s`;
}

const count = new Intl.NumberFormat("en");

// PRD-Studio RN-04: one run's progress and controls, under the list so Tab never climbs back up.
export function RunPanel({
  runId,
  onChanged,
}: {
  runId: string;
  onChanged: () => void;
}) {
  const [view, setView] = useState<RunWorkspace | null>(null);
  const [failed, setFailed] = useState(false);
  const [refusal, setRefusal] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const base = `/api/v1/runs/${encodeURIComponent(runId)}`;

  const [loads, setLoads] = useState(0);

  useEffect(() => {
    let active = true;
    fetch(`${base}/workspace`, { cache: "no-store" })
      .then(async (reply) => {
        if (!active) return;
        if (reply.ok) {
          setView(parseRunWorkspace(await reply.json()));
          setFailed(false);
        } else {
          await reply.text();
          setFailed(true);
        }
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
    };
  }, [base, loads]);

  // The version the panel loaded, never a fresh one: a stale press is refused, not retried.
  async function send(command: Command, version: number): Promise<void> {
    setBusy(true);
    setRefusal(null);
    const reply = await csrfFetch(`${base}/${command}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": crypto.randomUUID(),
      },
      body: JSON.stringify({ expected_version: version }),
    }).catch(() => null);
    setBusy(false);
    if (reply?.ok === true) {
      setLoads((value) => value + 1);
      onChanged();
      return;
    }
    const failure = (await reply?.json().catch(() => null)) as {
      code?: string;
      message?: string;
    } | null;
    setRefusal(
      failure?.code === "version_conflict"
        ? STALE
        : (failure?.message ?? "That could not be done. Nothing changed."),
    );
  }

  function reload(): void {
    setRefusal(null);
    setLoads((value) => value + 1);
  }

  if (failed)
    return (
      <p role="alert" className="text-sm">
        This run&apos;s details are unavailable.
      </p>
    );
  if (view === null)
    return (
      <p role="status" className="text-muted-foreground text-sm">
        Loading the run&apos;s details.
      </p>
    );
  const run = view.run;
  const commands = commandsFor(run.status);
  const spent = run.budget.spent_micro_usd + run.budget.reserved_micro_usd;
  const estimated =
    run.budget.reserved_micro_usd > 0 ||
    view.outstanding.unreported_charges > 0;
  const tasks = view.plan?.tasks ?? [];
  const title = view.objective ?? "Untitled run";
  return (
    <section
      id="run-panel"
      aria-labelledby="run-panel-heading"
      data-panel={run.id}
      data-version={run.version}
      className="space-y-5 rounded-xl border p-5"
    >
      <div className="space-y-1.5">
        <StateLine status={run.status} />
        <h2
          id="run-panel-heading"
          className="text-[15px] font-semibold break-words"
        >
          {title}
        </h2>
        <dl className="text-muted-foreground grid gap-x-3 gap-y-0.5 text-[12.5px] sm:grid-cols-[auto_1fr]">
          <dt>Expert</dt>
          <dd data-field="panel-expert" className="text-foreground">
            {view.expert?.name ?? "None, a direct goal"}
          </dd>
          <dt>Started</dt>
          <dd
            data-field="panel-started"
            className="text-foreground tabular-nums"
          >
            {run.created_at}
          </dd>
        </dl>
      </div>

      <div className="space-y-2">
        <h3 className="text-[13px] font-semibold">Plan</h3>
        {tasks.length === 0 ? (
          <p className="text-muted-foreground text-sm">No plan yet.</p>
        ) : (
          <ol data-field="panel-plan" className="space-y-2 text-[13.5px]">
            {tasks.map((task) => (
              <li
                key={task.id}
                data-task={task.id}
                data-marker={task.marker}
                className={cn(
                  "border-border rounded-lg border px-3.5 py-2.5",
                  task.marker === "current" && "border-foreground/40",
                )}
              >
                <p className="flex flex-wrap items-baseline gap-x-2">
                  <span
                    data-field="task-marker"
                    className={cn(
                      "text-[12px] font-medium",
                      task.marker === "to_do" && "text-muted-foreground",
                    )}
                  >
                    {MARKER_TEXT[task.marker]}
                  </span>
                  <span className="font-medium break-words">{task.title}</span>
                </p>
                <dl className="text-muted-foreground mt-1 grid gap-x-3 gap-y-0.5 text-[12.5px] sm:grid-cols-[auto_1fr]">
                  <dt>Tools</dt>
                  <dd
                    data-field="task-tools"
                    className="text-foreground font-mono break-words"
                  >
                    {task.tools.length === 0
                      ? "None used yet"
                      : task.tools.join(", ")}
                  </dd>
                  <dt>Wall time</dt>
                  <dd
                    data-field="task-wall"
                    className="text-foreground tabular-nums"
                  >
                    {wallTime(task.wall_seconds)}
                  </dd>
                </dl>
              </li>
            ))}
          </ol>
        )}
      </div>

      <dl className="grid gap-x-3 gap-y-1 text-[13px] sm:grid-cols-[auto_1fr]">
        <dt className="text-muted-foreground">Spend</dt>
        <dd data-field="panel-spend" className="tabular-nums">
          {estimated ? "≈ " : ""}
          {dollars(spent)} of {dollars(run.budget.limit_micro_usd)}
          {estimated ? ", estimated" : ""}
        </dd>
        <dt className="text-muted-foreground">Tokens</dt>
        <dd data-field="panel-tokens" className="tabular-nums">
          {count.format(view.usage.input_tokens)} in,{" "}
          {count.format(view.usage.output_tokens)} out
        </dd>
        <dt className="text-muted-foreground">Tool calls</dt>
        <dd data-field="panel-metered" className="tabular-nums">
          {view.metered_tool_calls} of {view.metered_tool_call_limit} metered
          tool calls
        </dd>
      </dl>

      <div className="flex flex-wrap items-center gap-2">
        <Link
          href={`/runs/${encodeURIComponent(run.id)}`}
          className={buttonVariants({ variant: "outline" })}
        >
          Open run
        </Link>
        {commands.map((command) => (
          <Button
            key={command}
            variant={command === "cancel" ? "outline" : "default"}
            disabled={busy}
            onClick={() => void send(command, run.version)}
          >
            {command === "pause" ? (
              <Pause aria-hidden="true" />
            ) : command === "resume" ? (
              <Play aria-hidden="true" />
            ) : null}
            {LABELS[command]}
          </Button>
        ))}
      </div>
      {refusal === null ? null : (
        <div
          role="alert"
          data-panel-refusal="true"
          className="flex flex-wrap items-start gap-2 text-sm"
        >
          <CircleAlert
            aria-hidden="true"
            className="text-destructive mt-0.5 size-4 shrink-0"
          />
          <span className="min-w-0 flex-1">{refusal}</span>
          {refusal === STALE ? (
            <Button variant="outline" size="sm" onClick={reload}>
              <RotateCw aria-hidden="true" />
              Reload the panel
            </Button>
          ) : null}
        </div>
      )}
    </section>
  );
}
