"use client";

import { parseExecutionView, type ExecutionView } from "@autobots/api-client";
import Link from "next/link";

import {
  ToolUseTable,
  ToolUsesState,
  useToolUses,
} from "@/components/tool-uses";
import { Card } from "@/components/ui/card";
import { LoadState } from "@/components/ui/load-state";
import { SectionLabel } from "@/components/ui/page-header";
import { backoff, type Loaded } from "@/lib/load";
import { useResource } from "@/lib/use-resource";
import { cn } from "@/lib/utils";

const POLL_MS = 1000;
const BACKOFF_CAP_MS = 15_000;
const TERMINAL = new Set(["succeeded", "failed", "cancelled"]);
const STATUS_TEXT: Record<string, string> = {
  waiting: "Waiting for its inputs",
  running: "Running now",
  waiting_approval: "Waiting for a person's approval",
  stopped_here: "Stopped here. See the run for why",
  not_run: "Didn't run",
  succeeded: "Succeeded",
  failed: "Failed",
  skipped: "Skipped, since its branch wasn't taken",
  blocked: "Blocked by a failure upstream",
};

/**
 * Polls once a second until the run ends. No reply, a 5xx or a reply that isn't the execution keeps
 * polling, each time more slowly up to 15 s (WBLD-08); a refusal stops, since reading again won't
 * change it.
 */
function nextPoll(
  loaded: Loaded<ExecutionView>,
  failures: number,
): number | null {
  if (loaded.kind === "ready") {
    return TERMINAL.has(loaded.value.run_status) ? null : POLL_MS;
  }
  return loaded.kind === "unavailable" || loaded.kind === "out_of_date"
    ? backoff(failures, POLL_MS, BACKOFF_CAP_MS)
    : null;
}

/** Shows what's saved. It only reads, so reconnecting can't start or repeat anything. */
export function WorkflowMonitor({ executionId }: { executionId: string }) {
  const { state, value: view } = useResource(
    `/api/v1/workflow-executions/${encodeURIComponent(executionId)}`,
    parseExecutionView,
    { poll: nextPoll },
  );
  const connection =
    state.kind === "ready" || state.kind === "loading"
      ? "live"
      : "reconnecting";
  if (
    state.kind === "signed_out" ||
    state.kind === "denied" ||
    state.kind === "not_found"
  ) {
    return (
      <LoadState
        state={state}
        what="this execution"
        notFound="That execution is not available."
      />
    );
  }
  // A mismatch says so beside the last known state, while polling goes on.
  const outdated =
    state.kind === "out_of_date" ? (
      <LoadState state={state} what="this execution" />
    ) : null;
  if (view === null) {
    return (
      <>
        {outdated}
        <p
          role="status"
          data-connection={connection}
          className="text-muted-foreground text-sm"
        >
          {connection === "reconnecting"
            ? "Reconnecting."
            : "Loading this execution."}
        </p>
      </>
    );
  }
  // The tool uses are read again only when the saved state changed, not on every poll
  // (PRD-Tool-Catalog TV-02, WBLD-08).
  const revision = JSON.stringify(view);
  return (
    <>
      {outdated}
      <Card aria-labelledby="binding-heading" className="space-y-3">
        <SectionLabel id="binding-heading">Binding</SectionLabel>
        <div className="flex flex-col gap-x-8 gap-y-2 text-sm @2xl:flex-row @2xl:flex-wrap @2xl:items-baseline">
          <p data-binding="true">
            Version {view.workflow_version}, hash{" "}
            <span className="font-mono text-[12.5px]">
              {view.graph_hash.slice(0, 12)}
            </span>
            .
          </p>
          <p role="status" data-run-status={view.run_status}>
            Run:{" "}
            <span className={cn("font-medium", tone(view.run_status))}>
              {view.run_status.replaceAll("_", " ")}
            </span>
            {view.stop_reason === null
              ? ""
              : `, ${view.stop_reason.replaceAll("_", " ")}`}
            .{" "}
            <Link
              href={`/runs/${view.run_id}`}
              className="font-medium underline"
            >
              Open the run
            </Link>
          </p>
          <p
            data-connection={connection}
            className={cn(
              "flex items-center gap-1.5 @2xl:ml-auto",
              connection === "reconnecting"
                ? "text-muted-foreground"
                : "text-foreground",
            )}
          >
            <span
              aria-hidden="true"
              className="size-1.5 shrink-0 rounded-full bg-current"
            />
            {connection === "reconnecting"
              ? "Reconnecting. Showing the last known state."
              : "Live"}
          </p>
        </div>
      </Card>
      <InstancesCard view={view} />
      <NodeToolUses
        runId={view.run_id}
        revision={revision}
        instances={view.instances.map((instance) => instance.key)}
      />
      <Card aria-labelledby="emissions-heading" className="space-y-3">
        <SectionLabel id="emissions-heading">Output emissions</SectionLabel>
        {view.emissions.length === 0 ? (
          <p className="text-muted-foreground text-sm">
            Nothing has been emitted yet.
          </p>
        ) : (
          <ul className="text-sm">
            {view.emissions.map((emission) => (
              <li
                key={`${emission.instance_key}-${emission.port}-${emission.sequence}`}
                data-emission={`${emission.instance_key}.${emission.port}.${emission.sequence}`}
                className="border-t py-2 wrap-anywhere first:border-t-0 first:pt-0"
              >
                <span className="font-mono text-[12.5px] font-medium">
                  {emission.instance_key}.{emission.port}
                  {emission.sequence === 0 ? "" : ` [${emission.sequence}]`}
                </span>
                :{" "}
                <code className="rounded-md border px-1.5 py-px font-mono text-[12.5px] dark:border-transparent dark:bg-muted">
                  {emission.value}
                </code>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}

function InstancesCard({ view }: { view: ExecutionView }) {
  return (
    <Card aria-labelledby="instances-heading" className="space-y-3">
      <SectionLabel id="instances-heading">Node instances</SectionLabel>
      <table className="w-full text-left text-[13.5px]">
        <thead>
          <tr className="border-b">
            <th
              scope="col"
              className="text-muted-foreground pr-3 pb-2.5 text-[12.5px] font-medium"
            >
              Instance
            </th>
            <th
              scope="col"
              className="text-muted-foreground px-3 pb-2.5 text-[12.5px] font-medium"
            >
              Block version
            </th>
            <th
              scope="col"
              className="text-muted-foreground pb-2.5 pl-3 text-[12.5px] font-medium"
            >
              Status
            </th>
          </tr>
        </thead>
        <tbody>
          {view.instances.map((instance) => (
            <tr
              key={instance.key}
              data-instance={instance.key}
              data-status={instance.status}
              className="border-b align-top last:border-b-0"
            >
              <td className="py-2.5 pr-3 font-mono text-[12.5px] font-medium wrap-anywhere">
                {instance.key}
              </td>
              <td className="px-3 py-2.5 font-mono text-[12.5px]">
                {view.block_versions[instance.node_id]}
              </td>
              <td className="py-2.5 pl-3">
                <span className="inline-flex items-baseline gap-2">
                  <span
                    aria-hidden="true"
                    className={cn(
                      "size-1.5 shrink-0 translate-y-[-1px] rounded-full bg-current",
                      tone(instance.status) || "text-muted-foreground",
                    )}
                  />
                  <span>
                    {STATUS_TEXT[instance.status] ?? instance.status}
                    {instance.error_code === null
                      ? ""
                      : `: ${instance.error_code.replaceAll("_", " ")}`}
                  </span>
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

// Colored words for a state, beside the words themselves (Decision 0021 R3–R4). Unknown states stay plain.
function tone(status: string): string {
  if (status === "succeeded") return "text-success-text";
  if (status === "failed" || status === "blocked") return "text-destructive";
  if (status === "waiting_approval") return "text-attention";
  if (status === "running") return "text-live-text";
  return "";
}

/** Tool uses under the node instance that made them. Nodes share their execution's run. */
function NodeToolUses({
  runId,
  revision,
  instances,
}: {
  runId: string;
  revision: string;
  instances: readonly string[];
}) {
  const read = useToolUses(runId, revision);
  const { uses } = read;
  const keys = [
    ...instances.filter((key) => uses?.some((use) => use.instance_key === key)),
  ];
  const outside = (uses ?? []).filter(
    (use) => use.instance_key === null || !instances.includes(use.instance_key),
  );
  return (
    <Card aria-labelledby="node-tools-heading" className="space-y-3">
      <SectionLabel id="node-tools-heading">Tool uses by node</SectionLabel>
      {uses === null || uses.length === 0 ? (
        <ToolUsesState uses={read} empty="No node has used a tool yet." />
      ) : (
        <>
          {keys.map((key) => (
            <section
              key={key}
              aria-labelledby={`node-tools-${key}`}
              data-node-tools={key}
              className="space-y-1.5 border-t pt-3"
            >
              <h3 id={`node-tools-${key}`} className="text-sm font-medium">
                Node <span className="font-mono text-[12.5px]">{key}</span>
              </h3>
              <ToolUseTable
                uses={uses.filter((use) => use.instance_key === key)}
                caption={`Tools node ${key} used, in order`}
              />
            </section>
          ))}
          {outside.length === 0 ? null : (
            <section
              aria-labelledby="node-tools-outside"
              data-node-tools="outside"
              className="space-y-1.5 border-t pt-3"
            >
              <h3 id="node-tools-outside" className="text-sm font-medium">
                Outside any node
              </h3>
              <ToolUseTable
                uses={outside}
                caption="Tools used outside a node, in order"
              />
            </section>
          )}
        </>
      )}
    </Card>
  );
}
