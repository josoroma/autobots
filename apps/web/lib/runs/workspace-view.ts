/**
 * The run page's view of a snapshot (R-49, WRUN-01): the counts and rules its regions show, and
 * their short texts, so the rules sit outside JSX where `node --test` reaches them. Presentation
 * only: every figure is the service's, and the page judges nothing. Pure and JSX-free.
 */
import type { RunWorkspace } from "@autobots/api-client";

import { summarizerDiffers } from "../model-roles.ts";
import type { Connection } from "./workspace-load.ts";

export interface WorkspaceView {
  /** Model calls with no settled charge, which the charge form asks the owner to record. */
  openCalls: number;
  /** Every known unknown. The Usage section lists them when there are any. */
  unsettled: number;
  /** The run waits for an approval decision, so the page links to Approvals. */
  awaitsApproval: boolean;
  /** The run would pause with route_not_bound if it needs compaction (WRUN-11). */
  summarizerDiffers: boolean;
  /** The context budget in thousands of tokens, as the Budgets section says it. */
  contextThousands: number;
}

export function toWorkspaceView(snapshot: RunWorkspace): WorkspaceView {
  const { uncertain_calls, unknown_effects, unreported_charges } =
    snapshot.outstanding;
  return {
    openCalls: uncertain_calls + unreported_charges,
    unsettled: uncertain_calls + unknown_effects + unreported_charges,
    awaitsApproval: snapshot.run.status === "waiting_approval",
    summarizerDiffers: summarizerDiffers(snapshot.role_map),
    contextThousands: Math.round(snapshot.budgets.context_tokens / 1000),
  };
}

const CONNECTION_TEXT: Readonly<Record<Connection, string>> = {
  loading: "Loading",
  live: "Live",
  reconnecting: "Reconnecting. Showing the last known state.",
  ended: "Finished. No more activity is expected.",
};

/** The stream's state under the status, as `data-connection` names it. */
export function connectionText(connection: Connection): string {
  return CONNECTION_TEXT[connection];
}

/** A verification requirement that wasn't met, such as `artifact:report_md`, in words. */
export function unmetText(item: string): string {
  return item.replaceAll("_", " ").replace(":", ": ");
}

export function expertTools(tools: readonly string[]): string {
  return tools.length === 0 ? "none" : tools.join(", ");
}

/** An Expert's own role bindings, or the workspace setting when it has none. */
export function expertModels(
  bindings: Readonly<Record<string, string>>,
): string {
  const entries = Object.entries(bindings);
  return entries.length === 0
    ? "the workspace setting"
    : entries.map(([role, profile]) => `${role}: ${profile}`).join(", ");
}

type Plan = NonNullable<RunWorkspace["plan"]>;

export function planNote(
  plan: Pick<Plan, "version" | "revision_reason">,
): string {
  return plan.revision_reason === null
    ? `Version ${plan.version}`
    : `Version ${plan.version}, revised because: ${plan.revision_reason}`;
}

export function taskProgress(
  task: Pick<Plan["tasks"][number], "status" | "evidence_summary">,
): string {
  const state = task.status === "complete" ? "complete" : "open";
  return task.evidence_summary === null
    ? state
    : `${state}. ${task.evidence_summary}`;
}

export function artifactFacts(
  artifact: Pick<RunWorkspace["artifacts"][number], "size_bytes" | "sha256">,
): string {
  return `${artifact.size_bytes} bytes, sha256 ${artifact.sha256.slice(0, 12)}`;
}
