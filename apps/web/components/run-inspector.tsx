"use client";

import { parseRunInspector, type RunInspector } from "@autobots/api-client";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Card } from "@/components/ui/card";

function dollars(micro: number): string {
  return `US$${micro / 1_000_000}`;
}

function tokens(value: number | null): string {
  return value === null ? "not reported" : String(value);
}

export function RunInspectorView({ runId }: { runId: string }) {
  const [view, setView] = useState<RunInspector | null>(null);
  const [state, setState] = useState<"loading" | "unavailable" | "error">(
    "loading",
  );

  useEffect(() => {
    let active = true;
    fetch(`/api/v1/runs/${encodeURIComponent(runId)}/inspector`, {
      cache: "no-store",
    })
      .then(async (reply) => {
        if (!active) return;
        if (reply.ok) {
          setView(parseRunInspector(await reply.json()));
          return;
        }
        await reply.text();
        setState(
          reply.status === 404 || reply.status === 401
            ? "unavailable"
            : "error",
        );
      })
      .catch(() => {
        if (active) setState("error");
      });
    return () => {
      active = false;
    };
  }, [runId]);

  if (view === null) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Run inspector</h1>
        {state === "loading" ? (
          <p role="status" data-state="loading" className="text-sm">
            Loading this run.
          </p>
        ) : (
          <p role="alert" data-state={state} className="text-sm">
            {state === "unavailable"
              ? "That run is not available. Sign in with access to it, or check the link."
              : "This run could not be read. Check that the local API is running."}
          </p>
        )}
      </div>
    );
  }
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Run inspector</h1>
      <p className="text-sm">
        {view.goal_summary === "" ? "Untitled run" : view.goal_summary}.{" "}
        <Link href={`/runs/${runId}`} className="font-medium underline">
          Back to the run
        </Link>
      </p>
      <Card aria-labelledby="calls-heading" className="space-y-3">
        <h2 id="calls-heading" className="text-lg font-medium">
          Model calls
        </h2>
        <p className="text-sm text-muted-foreground">
          This run and any child runs, since they share its budget.
        </p>
        {view.model_calls.length === 0 ? (
          <p className="text-sm">No model calls.</p>
        ) : (
          <ul className="space-y-3 text-sm">
            {view.model_calls.map((call) => (
              <li key={call.id} data-call={call.status} className="break-words">
                <p className="font-medium">
                  {call.role}, attempt {call.attempt}:{" "}
                  {call.outcome_unknown
                    ? "outcome unknown"
                    : call.charge_source_unknown
                      ? "reconciled"
                      : call.status.replaceAll("_", " ")}
                </p>
                <p>
                  Provider {call.provider}. Upstream{" "}
                  <span data-upstream="true">{call.upstream_provider}</span>.
                </p>
                <p>
                  Canonical{" "}
                  <span data-canonical="true">{call.canonical_id}</span>, wire{" "}
                  <span data-wire="true">{call.wire_id}</span>
                </p>
                <p>
                  Tokens: {tokens(call.input_tokens)} in,{" "}
                  {tokens(call.output_tokens)} out, of which{" "}
                  {tokens(call.reasoning_tokens)} reasoning.
                </p>
                {call.reconciled ? (
                  <p data-cost="entered">
                    Charge entered by the owner, from the provider&apos;s
                    records:{" "}
                    {call.reported_micro_usd === null
                      ? "none"
                      : dollars(call.reported_micro_usd)}
                  </p>
                ) : call.charge_source_unknown ? (
                  <p data-cost="unattributed">
                    Charge reconciled, source not recorded:{" "}
                    {call.reported_micro_usd === null
                      ? "none"
                      : dollars(call.reported_micro_usd)}
                  </p>
                ) : (
                  <p data-cost="reported">
                    Reported charge:{" "}
                    {call.reported_micro_usd === null
                      ? "none"
                      : dollars(call.reported_micro_usd)}
                  </p>
                )}
                <p data-cost="estimated">
                  Estimated worst case, not a charge:{" "}
                  {dollars(call.estimated_micro_usd)}
                </p>
                {call.failure_class === null ? null : (
                  <p data-error="true">
                    Error: {call.failure_class.replaceAll("_", " ")}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Card aria-labelledby="tools-heading" className="space-y-3">
        <h2 id="tools-heading" className="text-lg font-medium">
          Tool operation attempts
        </h2>
        <p className="text-sm text-muted-foreground">
          This run only. A child run shows its own.
        </p>
        {view.tool_attempts.length === 0 ? (
          <p className="text-sm">No tool operations.</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {view.tool_attempts.map((attempt) => (
              <li
                key={attempt.operation_id}
                data-tool={attempt.tool_id}
                data-tool-status={attempt.status}
              >
                {attempt.tool_id}, version {attempt.tool_version}:{" "}
                {attempt.status}
                {attempt.failure_code === null
                  ? ""
                  : ` (${attempt.failure_code})`}
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Card aria-labelledby="evidence-heading" className="space-y-3">
        <h2 id="evidence-heading" className="text-lg font-medium">
          Evidence
        </h2>
        {view.evidence.length === 0 ? (
          <p data-field="evidence" className="text-sm">
            No task has cited evidence.
          </p>
        ) : (
          <ul data-field="evidence" className="space-y-2 text-sm">
            {view.evidence.map((item) => (
              <li
                key={`${item.task_id}-${item.reference}`}
                className="break-words"
              >
                <p>
                  Task {item.task_id}: {item.summary}
                </p>
                <p>
                  {item.kind === "artifact" && item.artifact_id !== null ? (
                    <a
                      href={`/api/v1/artifacts/${item.artifact_id}/download`}
                      className="font-medium underline"
                    >
                      {item.reference}
                    </a>
                  ) : (
                    `${item.kind}: ${item.reference}`
                  )}
                </p>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Card aria-labelledby="checkpoints-heading" className="space-y-3">
        <h2 id="checkpoints-heading" className="text-lg font-medium">
          Checkpoints
        </h2>
        {view.checkpoints.length === 0 ? (
          <p className="text-sm">No checkpoints.</p>
        ) : (
          <ol className="space-y-1 text-sm">
            {view.checkpoints.map((checkpoint) => (
              <li
                key={checkpoint.checkpoint_id}
                data-checkpoint={checkpoint.checkpoint_id}
                className="break-all"
              >
                Step {checkpoint.step ?? "not recorded"},{" "}
                {checkpoint.source ?? "unknown source"}:{" "}
                {checkpoint.checkpoint_id}
              </li>
            ))}
          </ol>
        )}
        {view.checkpoints_truncated ? (
          <p className="text-muted-foreground text-sm">
            Showing the first {view.checkpoints.length} checkpoints.
          </p>
        ) : null}
      </Card>
    </div>
  );
}
