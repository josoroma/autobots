"use client";

import { parseRunInspector, type RunInspector } from "@autobots/api-client";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Card } from "@/components/ui/card";

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
        if (reply.ok) setView(parseRunInspector(await reply.json()));
        else if (reply.status === 404 || reply.status === 401)
          setState("unavailable");
        else setState("error");
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
        {view.model_calls.length === 0 ? (
          <p className="text-sm">No model calls.</p>
        ) : (
          <ul className="space-y-3 text-sm">
            {view.model_calls.map((call) => (
              <li key={call.id} data-call={call.status} className="break-words">
                <p className="font-medium">
                  {call.role}, attempt {call.attempt}: {call.status}
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
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Card aria-labelledby="tools-heading" className="space-y-3">
        <h2 id="tools-heading" className="text-lg font-medium">
          Tool operation attempts
        </h2>
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
