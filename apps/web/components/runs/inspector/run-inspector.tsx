import type { RunInspector } from "@autobots/api-client";
import Link from "next/link";

import {
  Checkpoints,
  Evidence,
  ToolAttempts,
} from "@/components/runs/inspector/inspector-lists";
import { ModelCalls } from "@/components/runs/inspector/model-calls";

// US-11.5: the run inspector, rendered on the server from the page's read (WRUN-14, R-67). It has
// no interaction, so none of it is sent to the browser as code.

/** The run's goal and the way back to it, under the page's title. */
export function InspectorLead({
  runId,
  view,
}: {
  runId: string;
  view: RunInspector;
}) {
  return (
    <>
      <span className="text-foreground font-document text-goal break-words">
        {view.goal_summary === "" ? "Untitled run" : view.goal_summary}.
      </span>{" "}
      <Link
        href={`/runs/${runId}`}
        className="text-foreground font-medium whitespace-nowrap underline underline-offset-4"
      >
        Back to the run
      </Link>
    </>
  );
}

/** Every model call, tool attempt, piece of evidence and checkpoint in the run's tree. */
export function RunInspectorView({ view }: { view: RunInspector }) {
  return (
    <>
      <ModelCalls calls={view.model_calls} />
      <ToolAttempts attempts={view.tool_attempts} />
      <Evidence items={view.evidence} />
      <Checkpoints view={view} />
    </>
  );
}
