"use client";

import { parseRunInspector } from "@autobots/api-client";
import Link from "next/link";

import {
  Checkpoints,
  Evidence,
  ToolAttempts,
} from "@/components/runs/inspector/inspector-lists";
import { ModelCalls } from "@/components/runs/inspector/model-calls";
import { LoadState } from "@/components/ui/load-state";
import { PageHeader } from "@/components/ui/page-header";
import { RUN_NOT_FOUND } from "@/lib/runs/workspace-load";
import { useResource } from "@/lib/use-resource";

// The run page's classification: a refusal, a missing run and a mismatch each say so, and only an
// outage offers Retry (WRUN-02, PRD-Development-Harness DH-06). It reads once; Retry reads again.
export function RunInspectorView({ runId }: { runId: string }) {
  const { state, pending, reload } = useResource(
    `/api/v1/runs/${encodeURIComponent(runId)}/inspector`,
    parseRunInspector,
  );
  if (state.kind !== "ready") {
    return (
      <div className="mx-auto max-w-4xl space-y-4">
        <PageHeader title="Run inspector" />
        <LoadState
          state={state}
          what="this run"
          onRetry={reload}
          pending={pending}
          notFound={RUN_NOT_FOUND}
        />
      </div>
    );
  }
  const view = state.value;
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header className="space-y-2">
        <h1 className="text-[32px] leading-tight">Run inspector</h1>
        <p className="text-muted-foreground text-sm leading-relaxed">
          <span className="text-foreground font-document text-[17px] break-words">
            {view.goal_summary === "" ? "Untitled run" : view.goal_summary}.
          </span>{" "}
          <Link
            href={`/runs/${runId}`}
            className="text-foreground font-medium whitespace-nowrap underline underline-offset-4"
          >
            Back to the run
          </Link>
        </p>
      </header>
      <ModelCalls calls={view.model_calls} />
      <ToolAttempts attempts={view.tool_attempts} />
      <Evidence items={view.evidence} />
      <Checkpoints view={view} />
    </div>
  );
}
