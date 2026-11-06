"use client";

import { parseExecutionView, type ExecutionView } from "@autobots/api-client";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Card } from "@/components/ui/card";

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
      <p role="status" data-connection={state} className="text-sm">
        {state === "reconnecting" ? "Reconnecting." : "Loading this execution."}
      </p>
    );
  }
  return (
    <>
      <Card aria-labelledby="binding-heading" className="space-y-2">
        <h2 id="binding-heading" className="text-lg font-medium">
          Binding
        </h2>
        <p data-binding="true" className="text-sm">
          Version {view.workflow_version}, hash {view.graph_hash.slice(0, 12)}.
        </p>
        <p role="status" data-run-status={view.run_status} className="text-sm">
          Run: {view.run_status.replaceAll("_", " ")}
          {view.stop_reason === null
            ? ""
            : `, ${view.stop_reason.replaceAll("_", " ")}`}
          .{" "}
          <Link href={`/runs/${view.run_id}`} className="underline">
            Open the run
          </Link>
        </p>
        <p data-connection={state} className="text-muted-foreground text-sm">
          {state === "reconnecting"
            ? "Reconnecting. Showing the last known state."
            : "Live"}
        </p>
      </Card>
      <Card aria-labelledby="instances-heading" className="space-y-2">
        <h2 id="instances-heading" className="text-lg font-medium">
          Node instances
        </h2>
        <table className="w-full text-left text-sm">
          <thead>
            <tr>
              <th scope="col">Instance</th>
              <th scope="col">Block version</th>
              <th scope="col">Status</th>
            </tr>
          </thead>
          <tbody>
            {view.instances.map((instance) => (
              <tr
                key={instance.key}
                data-instance={instance.key}
                data-status={instance.status}
              >
                <td className="py-1 font-medium">{instance.key}</td>
                <td>{String(view.block_versions[instance.node_id])}</td>
                <td>
                  {STATUS_TEXT[instance.status] ?? instance.status}
                  {instance.error_code === null
                    ? ""
                    : `: ${instance.error_code.replaceAll("_", " ")}`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <Card aria-labelledby="emissions-heading" className="space-y-2">
        <h2 id="emissions-heading" className="text-lg font-medium">
          Output emissions
        </h2>
        {view.emissions.length === 0 ? (
          <p className="text-sm">Nothing has been emitted yet.</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {view.emissions.map((emission) => (
              <li
                key={`${emission.instance_key}-${emission.port}-${emission.sequence}`}
                data-emission={`${emission.instance_key}.${emission.port}.${emission.sequence}`}
              >
                <span className="font-medium">
                  {emission.instance_key}.{emission.port}
                  {emission.sequence === 0 ? "" : ` [${emission.sequence}]`}
                </span>
                : <code>{emission.value}</code>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}
