import type { WorkflowExecutionList } from "@autobots/api-client";
import Link from "next/link";

import { formatRelative } from "@/lib/format";
import { runStatusText } from "@/lib/runs/status";
import { durationText, spendText } from "@/lib/workflows/list";

/** Each recent execution's version, state, spend, wall time and start (PRD-Studio WF-04). */
export function RecentExecutions({
  executions,
  now,
}: {
  executions: WorkflowExecutionList["executions"];
  /** When the list was read, in epoch milliseconds. */
  now: number;
}) {
  if (executions.length === 0) {
    return <p className="text-muted-foreground text-sm">No executions yet.</p>;
  }
  return (
    <ul className="text-ui">
      {executions.map((execution) => (
        <li
          key={execution.id}
          data-execution={execution.id}
          className="flex flex-wrap gap-x-3 gap-y-0.5 border-t py-2"
        >
          <Link
            href={`/runs/${execution.run_id}`}
            className="font-medium underline-offset-4 hover:underline"
          >
            Version {execution.version}
          </Link>
          <span data-field="state">{runStatusText(execution.status)}</span>
          <span data-field="spend" className="tabular-nums">
            {spendText(execution)}
          </span>
          <span
            data-field="duration"
            className="text-muted-foreground tabular-nums"
          >
            {durationText(execution.duration_seconds)}
          </span>
          <time
            dateTime={execution.started_at}
            className="text-muted-foreground"
          >
            {formatRelative(execution.started_at, now)}
          </time>
        </li>
      ))}
    </ul>
  );
}
