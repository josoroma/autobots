/**
 * A browse's steps in the run's Tools used table (Decision 0035 Y11, US-17.4): how many it kept,
 * where each one's screenshot is read from, and how a step reads. Each page and submit is a host and
 * path only, never a typed value or a query.
 */
import type { BrowseStep, ToolUseView } from "@autobots/api-client";

/** The steps a browse_goal use took, from its public output, or 0 for any other use. */
export function browseStepCount(use: ToolUseView): number {
  if (use.tool_id !== "browse_goal") return 0;
  const steps = use.output_public?.["steps"];
  return typeof steps === "number" && Number.isInteger(steps) && steps > 0
    ? steps
    : 0;
}

/** The BFF route that serves one step's screenshot to a member of the run's workspace. */
export function screenshotUrl(
  runId: string,
  useId: number,
  step: number,
): string {
  return `/api/v1/runs/${encodeURIComponent(runId)}/tool-uses/${useId}/steps/${step}/screenshot`;
}

export function stepTitle(step: BrowseStep): string {
  return `Step ${step.step}: ${step.page ?? "no page"}`;
}

export function screenshotAlt(step: BrowseStep): string {
  return `Screenshot after step ${step.step}${step.page === null || step.page === undefined ? "" : `, on ${step.page}`}`;
}

export function stepsLabel(count: number): string {
  return count === 1 ? "Show 1 step" : `Show ${count} steps`;
}
