import type { ToolUseView } from "@autobots/api-client";
import {
  Ban,
  CircleAlert,
  CircleCheck,
  CircleDashed,
  CircleHelp,
} from "lucide-react";

import type { ToolUses } from "@/components/runs/tool-uses/use-tool-uses";
import { LoadEmpty, LoadState } from "@/components/ui/load-state";
import {
  brief,
  toolOutcome,
  toolResult,
  toolUseWhen,
} from "@/lib/runs/tool-uses";
import { cn } from "@/lib/utils";

// PRD-Tool-Catalog TV-01 to TV-03: when, which tool, why (the plan task), for what, and outcome.
// Only public fields, digests and sizes reach this page; content never does.

const HEAD = "px-3 py-2 font-medium";
const CELL = "px-3 py-2.5";
const COLUMNS = ["When", "Tool", "Plan task", "Inputs", "Result", "Outcome"];

const ICON = "mt-0.5 size-3.5 shrink-0";

// Decorative: the outcome's words beside it carry the meaning.
function OutcomeIcon({ outcome }: { outcome: ToolUseView["outcome"] }) {
  switch (outcome) {
    case "succeeded":
      return (
        <CircleCheck
          aria-hidden="true"
          className={cn(ICON, "text-success-text")}
        />
      );
    case "failed":
      return (
        <CircleAlert
          aria-hidden="true"
          className={cn(ICON, "text-destructive")}
        />
      );
    case "unknown":
      return (
        <CircleHelp aria-hidden="true" className={cn(ICON, "text-attention")} />
      );
    case "denied":
      return (
        <Ban aria-hidden="true" className={cn(ICON, "text-muted-foreground")} />
      );
    case null:
      return (
        <CircleDashed
          aria-hidden="true"
          className={cn(ICON, "text-muted-foreground")}
        />
      );
  }
}

/** Loading, or why the uses can't be shown, until the first read succeeds. */
export function ToolUsesState({
  uses,
  empty,
}: {
  uses: ToolUses;
  empty: string;
}) {
  if (uses.uses === null) {
    return (
      <LoadState
        state={uses.failure ?? { kind: "loading" }}
        what="tool uses"
        onRetry={uses.reload}
        pending={uses.pending}
      />
    );
  }
  return <LoadEmpty className="text-muted-foreground">{empty}</LoadEmpty>;
}

export function ToolUseTable({
  uses,
  caption,
}: {
  uses: readonly ToolUseView[];
  caption: string;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm" data-tool-uses="true">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="text-muted-foreground border-b text-xs">
            {COLUMNS.map((column, index) => (
              <th
                key={column}
                scope="col"
                className={index === 0 ? cn(HEAD, "pl-0") : HEAD}
              >
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {uses.map((use) => (
            <ToolUseRow key={use.id} use={use} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ToolUseRow({ use }: { use: ToolUseView }) {
  return (
    <tr
      data-tool-use={use.id}
      data-tool-id={use.tool_id}
      data-outcome={use.outcome ?? "open"}
      className="border-b align-top last:border-b-0"
    >
      <td
        className={cn(
          CELL,
          "text-muted-foreground pl-0 text-xs whitespace-nowrap tabular-nums",
        )}
      >
        {toolUseWhen(use)}
      </td>
      <th scope="row" className={cn(CELL, "font-normal")}>
        <code className="font-mono text-[13px] font-medium">{use.tool_id}</code>
        {use.tool_version === null ? "" : ` v${use.tool_version}`}
        {use.group === null ? null : (
          <span className="text-muted-foreground block text-xs">
            {use.group.replaceAll("_", " ")}
          </span>
        )}
      </th>
      <td className={CELL} data-field="task">
        {use.task_title ?? "No plan task"}
      </td>
      <td
        className={cn(CELL, "font-mono text-xs break-all")}
        data-field="inputs"
      >
        {brief(use.input_public) || "Not shown"}
      </td>
      <td
        className={cn(CELL, "font-mono text-xs break-all")}
        data-field="result"
      >
        {toolResult(use)}
      </td>
      <td className={CELL} data-field="outcome">
        <span className="inline-flex items-start gap-1.5">
          <OutcomeIcon outcome={use.outcome} />
          {toolOutcome(use)}
        </span>
      </td>
    </tr>
  );
}
