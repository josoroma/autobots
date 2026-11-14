/**
 * The run requests and workflow graphs the suites arrange, typed against the generated contract
 * (TWEB-13).
 */
import type {
  RunRequest,
  WorkflowGraph,
  WorkflowLink,
  WorkflowNode,
} from "@autobots/api-client";

/**
 * The words tests/web/fixture_worker.py looks for in a goal, and what each makes the scripted
 * worker do. A goal without one runs plainly to success.
 */
export const WorkerScenario = {
  /** The worker is killed once before publishing, so recovery pauses at an uncertain call. */
  complete: "slice-complete",
  /** Never publishes the required artifact. */
  noArtifact: "slice-no-artifact",
  /** Writes a total one too high, so the artifact check fails. */
  wrongTotal: "slice-wrong-total",
  /** Answers without a plan, so the run fails with "plan missing". */
  onlyClaims: "slice-only-claims",
  /** Each model call waits, so a person can pause, resume and cancel the run while it runs. */
  slow: "slice-slow",
  /** Killed once before publishing, as `complete` is, under a marker of its own. */
  uncertain: "slice-uncertain",
  /** Each reply carries reasoning_details holding PROTECTED-REASONING, which must stay private. */
  reasoned: "slice-reasoned",
  /** One model call fails with a provider error, once per worker, before the provider accepts it. */
  failedCall: "slice-failed-call",
} as const;

/** A goal the worker compacts, matched with its stamp. */
export function compactingGoal(stamp: number): string {
  return `slice-compact-${stamp}`;
}

/** A goal whose run assigns a part to the Expert named. */
export function delegatingGoal(expertId: string): string {
  return `slice-delegate expert=${expertId}`;
}

/**
 * The run that sums two counts into report.md, which every scenario above works on. Its goal
 * starts with `scenario`, and the counts default to 2 and 3, so the report must say "Total: 5".
 */
export function twoCountsRun(
  scenario: string,
  { first = 2, second = 3 }: { first?: number; second?: number } = {},
): RunRequest {
  return {
    goal_text: `${scenario}: report the total of the two counts`,
    limit_micro_usd: 1_000_000,
    acceptance_criteria: ["The report states the correct total"],
    required_artifacts: [
      { name: "report.md", must_contain: [`Total: ${first + second}`] },
    ],
    input_documents: [
      {
        path: "inputs/data.md",
        content: `apples: ${first}\npears: ${second}\n`,
      },
    ],
  };
}

/** A workflow node at its block's version 1. */
export function node(
  id: string,
  block: string,
  config: Record<string, unknown> = {},
): WorkflowNode {
  return { id, block, version: 1, config };
}

/** A link from one node's output port to another's input port. */
export function link(
  source: string,
  sourcePort: string,
  target: string,
  targetPort: string,
): WorkflowLink {
  return { source, source_port: sourcePort, target, target_port: targetPort };
}

/** The smallest valid graph: a string input straight to the output. */
export function inToOut(): WorkflowGraph {
  return {
    nodes: [node("in", "input", { type: "string" }), node("out", "output")],
    links: [link("in", "value", "out", "value")],
  };
}
