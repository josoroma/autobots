"use client";

import { parseExecutionView, type ExecutionView } from "@autobots/api-client";
import Link from "next/link";
import { useEffect, useState } from "react";

import { ToolUseTable, useToolUses } from "@/components/tool-uses";
import { Card } from "@/components/ui/card";
import { SectionLabel } from "@/components/ui/page-header";
import { cn } from "@/lib/utils";

const POLL_MS = 1000;
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

/** Shows what's saved. It only reads, so reconnecting can't start or repeat anything. */
export function WorkflowMonitor({ executionId }: { executionId: string }) {
  const [view, setView] = useState<ExecutionView | null>(null);
  const [state, setState] = useState<"live" | "reconnecting" | "unavailable">(
    "live",
  );
  // Each saved state read again also reads the tool uses again (TV-02).
  const [loads, setLoads] = useState(0);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const load = async (): Promise<void> => {
      const reply = await fetch(
        `/api/v1/workflow-executions/${encodeURIComponent(executionId)}`,
        { cache: "no-store" },
      ).catch(() => null);
      if (!active) return;
      if (reply === null || reply.status >= 500) {
        setState("reconnecting");
      } else if (!reply.ok) {
        setState("unavailable");
        return;
      } else {
        const next = await reply
          .json()
          .then(parseExecutionView)
          .catch(() => null);
        if (!active) return;
        if (next === null) {
          setState("reconnecting");
        } else {
          setView(next);
          setLoads((count) => count + 1);
          setState("live");
          if (TERMINAL.has(next.run_status)) return;
        }
      }
      timer = setTimeout(() => void load(), POLL_MS);
    };
    void load();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [executionId]);

  if (state === "unavailable") {
    return (
      <p role="alert" data-state="unavailable" className="text-sm">
        That execution is not available.
      </p>
    );
  }
  if (view === null) {
    return (
      <p
        role="status"
        data-connection={state}
        className="text-muted-foreground text-sm"
      >
        {state === "reconnecting" ? "Reconnecting." : "Loading this execution."}
      </p>
    );
  }
  return (
    <>
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
            data-connection={state}
            className={cn(
              "flex items-center gap-1.5 @2xl:ml-auto",
              state === "reconnecting"
                ? "text-muted-foreground"
                : "text-foreground",
            )}
          >
            <span
              aria-hidden="true"
              className="size-1.5 shrink-0 rounded-full bg-current"
            />
            {state === "reconnecting"
              ? "Reconnecting. Showing the last known state."
              : "Live"}
          </p>
        </div>
      </Card>
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
      <NodeToolUses
        runId={view.run_id}
        version={loads}
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
  version,
  instances,
}: {
  runId: string;
  version: number;
  instances: readonly string[];
}) {
  const { uses, failed } = useToolUses(runId, version);
  const keys = [
    ...instances.filter((key) => uses?.some((use) => use.instance_key === key)),
  ];
  const outside = (uses ?? []).filter(
    (use) => use.instance_key === null || !instances.includes(use.instance_key),
  );
  return (
    <Card aria-labelledby="node-tools-heading" className="space-y-3">
      <SectionLabel id="node-tools-heading">Tool uses by node</SectionLabel>
      {failed && uses === null ? (
        <p role="alert" className="text-sm">
          Tool uses aren&apos;t available right now.
        </p>
      ) : uses === null ? (
        <p className="text-muted-foreground text-sm">Loading tool uses.</p>
      ) : uses.length === 0 ? (
        <p className="text-muted-foreground text-sm">
          No node has used a tool yet.
        </p>
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
