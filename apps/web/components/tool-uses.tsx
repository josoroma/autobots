"use client";

import { parseToolUseList, type ToolUseView } from "@autobots/api-client";
import {
  CircleAlert,
  CircleCheck,
  CircleDashed,
  CircleHelp,
  Ban,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { LoadEmpty, LoadState } from "@/components/ui/load-state";
import { loadJson, type LoadFailure } from "@/lib/load";
import { cn } from "@/lib/utils";

// PRD-Tool-Catalog TV-01 to TV-03: when, which tool, why (the plan task), for what, and outcome.
// Only public fields, digests and sizes reach this page; content never does.

const OUTCOMES: Record<string, string> = {
  succeeded: "Succeeded",
  failed: "Failed",
  unknown: "Outcome unknown",
  denied: "Denied",
};

const HEAD = "px-3 py-2 font-medium";
const CELL = "px-3 py-2.5";

// Decorative: the outcome's words beside it carry the meaning.
function OutcomeIcon({ outcome }: { outcome: string | null }) {
  const shared = "mt-0.5 size-3.5 shrink-0";
  if (outcome === "succeeded") {
    return (
      <CircleCheck
        aria-hidden="true"
        className={cn(shared, "text-success-text")}
      />
    );
  }
  if (outcome === "failed") {
    return (
      <CircleAlert
        aria-hidden="true"
        className={cn(shared, "text-destructive")}
      />
    );
  }
  if (outcome === "unknown") {
    return (
      <CircleHelp aria-hidden="true" className={cn(shared, "text-attention")} />
    );
  }
  if (outcome === "denied") {
    return (
      <Ban aria-hidden="true" className={cn(shared, "text-muted-foreground")} />
    );
  }
  return (
    <CircleDashed
      aria-hidden="true"
      className={cn(shared, "text-muted-foreground")}
    />
  );
}

function when(use: ToolUseView): string {
  const time = new Date(use.requested_at).toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  return use.duration_ms === null ? time : `${time}, ${use.duration_ms} ms`;
}

function brief(values: Record<string, unknown> | null): string {
  if (values === null || Object.keys(values).length === 0) return "";
  return Object.entries(values)
    .map(([key, value]) => {
      const text = typeof value === "string" ? value : JSON.stringify(value);
      return `${key}: ${text.length > 80 ? `${text.slice(0, 79)}…` : text}`;
    })
    .join("; ");
}

function result(use: ToolUseView): string {
  const shown = brief(use.output_public);
  if (shown !== "") return shown;
  if (use.output_bytes !== null) return `${use.output_bytes} bytes, not shown`;
  return "Nothing returned";
}

function outcome(use: ToolUseView): string {
  if (use.outcome === null) return "Not finished";
  const text = OUTCOMES[use.outcome] ?? use.outcome;
  return use.code === null ? text : `${text}: ${use.code.replaceAll("_", " ")}`;
}

export interface ToolUses {
  uses: ToolUseView[] | null;
  /** Why the newest read failed. Uses already shown stay shown. */
  failure: LoadFailure | null;
  pending: boolean;
  reload: () => void;
}

/**
 * Every page of a run's uses, read again whenever `version` changes. A caller passes a value that
 * changes only when the uses may have, so a poll that finds nothing new reads nothing (WBLD-08).
 */
export function useToolUses(runId: string, version: number | string): ToolUses {
  const [request, setRequest] = useState(0);
  const key = `${request}|${runId}|${version}`;
  const [state, setState] = useState<{
    key: string;
    uses: ToolUseView[] | null;
    failure: LoadFailure | null;
  }>({ key: "", uses: null, failure: null });
  useEffect(() => {
    // A newer read replaces this one, so this one is aborted rather than left open.
    const controller = new AbortController();
    const load = async (): Promise<void> => {
      const all: ToolUseView[] = [];
      let after = 0;
      for (;;) {
        const page = await loadJson(
          `/api/v1/runs/${encodeURIComponent(runId)}/tool-uses?after=${after}&limit=200`,
          parseToolUseList,
          { signal: controller.signal },
        );
        if (controller.signal.aborted) return;
        if (page.kind !== "ready") {
          setState((current) => ({ ...current, key, failure: page }));
          return;
        }
        all.push(...page.value.uses);
        if (page.value.next_cursor === null) break;
        after = page.value.next_cursor;
      }
      setState({ key, uses: all, failure: null });
    };
    void load();
    return () => controller.abort();
  }, [runId, key]);
  const reload = useCallback(() => setRequest((count) => count + 1), []);
  return {
    uses: state.uses,
    failure: state.failure,
    pending: state.key !== key,
    reload,
  };
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
            <th scope="col" className={cn(HEAD, "pl-0")}>
              When
            </th>
            <th scope="col" className={HEAD}>
              Tool
            </th>
            <th scope="col" className={HEAD}>
              Plan task
            </th>
            <th scope="col" className={HEAD}>
              Inputs
            </th>
            <th scope="col" className={HEAD}>
              Result
            </th>
            <th scope="col" className={HEAD}>
              Outcome
            </th>
          </tr>
        </thead>
        <tbody>
          {uses.map((use) => (
            <tr
              key={use.id}
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
                {when(use)}
              </td>
              <th scope="row" className={cn(CELL, "font-normal")}>
                <code className="font-mono text-[13px] font-medium">
                  {use.tool_id}
                </code>
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
                {result(use)}
              </td>
              <td className={CELL} data-field="outcome">
                <span className="inline-flex items-start gap-1.5">
                  <OutcomeIcon outcome={use.outcome} />
                  {outcome(use)}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** The run workspace's section. `version` changes when a tool-use event arrives. */
export function ToolsUsed({
  runId,
  version,
}: {
  runId: string;
  version: number;
}) {
  const read = useToolUses(runId, version);
  const { uses } = read;
  const latest = uses?.at(-1);
  return (
    <section
      aria-labelledby="tools-used-heading"
      className="space-y-3 border-t pt-6"
    >
      <h2 id="tools-used-heading" className="text-sm font-semibold">
        Tools used
      </h2>
      <p className="sr-only" aria-live="polite" data-field="tool-announcement">
        {latest === undefined
          ? ""
          : `${latest.tool_id}: ${outcome(latest)}. ${uses?.length ?? 0} tool uses.`}
      </p>
      {uses === null || uses.length === 0 ? (
        <ToolUsesState uses={read} empty="No tool has been used yet." />
      ) : (
        <ToolUseTable uses={uses} caption="Tools this run used, in order" />
      )}
    </section>
  );
}
