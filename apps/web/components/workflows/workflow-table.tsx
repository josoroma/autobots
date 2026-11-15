import type { WorkflowView } from "@autobots/api-client";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { formatRelative } from "@/lib/format";
import { runStatusText } from "@/lib/runs/status";
import { cn } from "@/lib/utils";

const TH = "text-muted-foreground px-3 pb-2.5 text-meta font-medium";
const TD = "px-3 py-3.5 align-top";
// At 400% zoom the list keeps the name, version and Preview, so nothing scrolls sideways.
const NARROW_HIDDEN = "hidden @xl:table-cell";

/** The published version, or that none is, and whether a draft is saved. */
function VersionBadges({ workflow }: { workflow: WorkflowView }) {
  return (
    <span className="flex flex-wrap gap-1.5">
      {workflow.latest_version === 0 ? (
        <Badge variant="attention" dot>
          Not published
        </Badge>
      ) : (
        <Badge variant="outline">Version {workflow.latest_version}</Badge>
      )}
      {workflow.draft === null ? null : (
        <Badge variant="attention" data-field="has-draft">
          Draft
        </Badge>
      )}
    </span>
  );
}

/** The last execution's state and when it started, or that it never ran. */
function LastExecution({
  workflow,
  now,
}: {
  workflow: WorkflowView;
  now: number;
}) {
  const last = workflow.last_execution;
  if (last === null) {
    return <span className="text-muted-foreground">Never run</span>;
  }
  return (
    <>
      {runStatusText(last.status)}
      <span className="text-muted-foreground">
        {", "}
        <time dateTime={last.started_at}>
          {formatRelative(last.started_at, now)}
        </time>
      </span>
    </>
  );
}

/** One workflow's row: its facts and its Preview link (PRD-Studio WF-01). */
function WorkflowRow({
  workflow,
  previewHref,
  selected,
  now,
}: {
  workflow: WorkflowView;
  previewHref: string;
  selected: boolean;
  now: number;
}) {
  return (
    <tr data-workflow={workflow.id} className="border-b">
      <td className={cn(TD, "pl-0")}>
        <Link
          href={`/workflows/${workflow.id}`}
          className="font-medium wrap-anywhere underline-offset-4 hover:underline"
        >
          {workflow.name}
        </Link>
        {workflow.description === null ? null : (
          <p
            data-field="description"
            className="text-muted-foreground mt-0.5 text-meta wrap-anywhere"
          >
            {workflow.description}
          </p>
        )}
      </td>
      <td data-field="experts" className={cn(TD, NARROW_HIDDEN, "text-meta")}>
        {workflow.experts.length === 0 ? (
          <span className="text-muted-foreground">None</span>
        ) : (
          workflow.experts.join(" → ")
        )}
      </td>
      <td className={TD}>
        <VersionBadges workflow={workflow} />
      </td>
      <td
        data-field="steps"
        className={cn(TD, NARROW_HIDDEN, "text-right tabular-nums")}
      >
        {workflow.step_count}
      </td>
      <td
        data-field="last-execution"
        className={cn(TD, NARROW_HIDDEN, "text-meta")}
      >
        <LastExecution workflow={workflow} now={now} />
      </td>
      <td
        data-field="runs"
        className={cn(TD, NARROW_HIDDEN, "text-right tabular-nums")}
      >
        {workflow.run_count}
      </td>
      <td className={cn(TD, "pr-0 text-right")}>
        <Link
          href={previewHref}
          scroll={false}
          aria-current={selected ? "true" : undefined}
          aria-label={`Preview ${workflow.name}`}
          className="text-ui underline underline-offset-4"
        >
          Preview
        </Link>
      </td>
    </tr>
  );
}

/** The shown workflows as a table, in a scroll region a keyboard reaches and screen readers name. */
export function WorkflowTable({
  rows,
  selected,
  previewHref,
  now,
}: {
  rows: readonly WorkflowView[];
  selected: string | null;
  previewHref: (workflowId: string) => string;
  /** When the list was read, in epoch milliseconds. */
  now: number;
}) {
  return (
    <div
      tabIndex={0}
      role="region"
      aria-label="Workflows table"
      className="overflow-x-auto"
    >
      <table className="w-full text-left text-body">
        <thead>
          <tr className="border-b">
            <th scope="col" className={cn(TH, "pl-0")}>
              Workflow
            </th>
            <th scope="col" className={cn(TH, NARROW_HIDDEN)}>
              Experts
            </th>
            <th scope="col" className={TH}>
              Version
            </th>
            <th scope="col" className={cn(TH, NARROW_HIDDEN, "text-right")}>
              Steps
            </th>
            <th scope="col" className={cn(TH, NARROW_HIDDEN)}>
              Last execution
            </th>
            <th scope="col" className={cn(TH, NARROW_HIDDEN, "text-right")}>
              Runs
            </th>
            <th scope="col" className={cn(TH, "pr-0")}>
              <span className="sr-only">Preview</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((workflow) => (
            <WorkflowRow
              key={workflow.id}
              workflow={workflow}
              previewHref={previewHref(workflow.id)}
              selected={workflow.id === selected}
              now={now}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}
