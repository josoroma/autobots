import type { RunWorkspace } from "@autobots/api-client";

import { StateLine } from "@/components/runs/run-state";
import { spendOf } from "@/lib/budget";
import { formatDuration, formatInstant, formatUsd } from "@/lib/format";
import { cn } from "@/lib/utils";

type Task = NonNullable<RunWorkspace["plan"]>["tasks"][number];

const MARKER_TEXT: Record<Task["marker"], string> = {
  done: "Done",
  current: "Current",
  to_do: "To do",
};

const count = new Intl.NumberFormat("en");

/** The run's state, its goal as the panel's heading, its Expert and when it started. */
export function PanelSummary({ view }: { view: RunWorkspace }) {
  const run = view.run;
  return (
    <div className="space-y-1.5">
      <StateLine status={run.status} />
      <h2
        id="run-panel-heading"
        className="text-[15px] font-semibold break-words"
      >
        {view.objective ?? "Untitled run"}
      </h2>
      <dl className="text-muted-foreground grid gap-x-3 gap-y-0.5 text-[12.5px] sm:grid-cols-[auto_1fr]">
        <dt>Expert</dt>
        <dd data-field="panel-expert" className="text-foreground">
          {view.expert?.name ?? "None, a direct goal"}
        </dd>
        <dt>Started</dt>
        <dd data-field="panel-started" className="text-foreground tabular-nums">
          {formatInstant(run.created_at)}
        </dd>
      </dl>
    </div>
  );
}

/** RN-04's plan: each task done, current or to do, with its tools and wall time. */
export function PanelPlan({ tasks }: { tasks: readonly Task[] }) {
  return (
    <div className="space-y-2">
      <h3 className="text-[13px] font-semibold">Plan</h3>
      {tasks.length === 0 ? (
        <p className="text-muted-foreground text-sm">No plan yet.</p>
      ) : (
        <ol data-field="panel-plan" className="space-y-2 text-[13.5px]">
          {tasks.map((task) => (
            <PanelTask key={task.id} task={task} />
          ))}
        </ol>
      )}
    </div>
  );
}

function PanelTask({ task }: { task: Task }) {
  return (
    <li
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
          {task.tools.length === 0 ? "None used yet" : task.tools.join(", ")}
        </dd>
        <dt>Wall time</dt>
        <dd data-field="task-wall" className="text-foreground tabular-nums">
          {task.wall_seconds === null ? "—" : formatDuration(task.wall_seconds)}
        </dd>
      </dl>
    </li>
  );
}

/** Spend, an estimate while a charge is unsettled (RN-03), tokens and metered tool calls. */
export function PanelFacts({ view }: { view: RunWorkspace }) {
  const { budget } = view.run;
  const { micro: spent, estimated } = spendOf(
    budget.spent_micro_usd,
    budget.reserved_micro_usd,
    view.outstanding.unreported_charges > 0,
  );
  return (
    <dl className="grid gap-x-3 gap-y-1 text-[13px] sm:grid-cols-[auto_1fr]">
      <dt className="text-muted-foreground">Spend</dt>
      <dd data-field="panel-spend" className="tabular-nums">
        {estimated ? "≈ " : ""}
        {formatUsd(spent)} of {formatUsd(budget.limit_micro_usd)}
        {estimated ? ", estimated" : ""}
      </dd>
      <dt className="text-muted-foreground">Tokens</dt>
      <dd data-field="panel-tokens" className="tabular-nums">
        {count.format(view.usage.input_tokens)} in,{" "}
        {count.format(view.usage.output_tokens)} out
      </dd>
      <dt className="text-muted-foreground">Tool calls</dt>
      <dd data-field="panel-metered" className="tabular-nums">
        {view.metered_tool_calls} of {view.metered_tool_call_limit} metered tool
        calls
      </dd>
    </dl>
  );
}
