/**
 * The Workflows list's rules (WBLD-11): its tabs (PRD-Studio WF-01), which version a preview shows
 * (PRD-Studio WF-03), and an execution's spend and duration (PRD-Studio WF-04). Pure and JSX-free,
 * so `node --test` covers it.
 */
import type {
  WorkflowExecutionSummary,
  WorkflowView,
} from "@autobots/api-client";

import { spendOf } from "../budget.ts";
import { formatDuration, formatUsd } from "../format.ts";

export type WorkflowTab = "all" | "published" | "drafts";

export const WORKFLOW_TABS: readonly { id: WorkflowTab; label: string }[] = [
  { id: "all", label: "All" },
  { id: "published", label: "Published" },
  { id: "drafts", label: "Drafts" },
];

export const WORKFLOW_TAB_IDS: readonly WorkflowTab[] = WORKFLOW_TABS.map(
  (tab) => tab.id,
);

/** Whether a tab holds a workflow: Published once a version is, Drafts while a draft is saved. */
export function inWorkflowTab(
  workflow: Pick<WorkflowView, "latest_version" | "draft">,
  tab: WorkflowTab,
): boolean {
  if (tab === "all") return true;
  return tab === "published"
    ? workflow.latest_version > 0
    : workflow.draft !== null;
}

/** The version a preview shows: the one asked for, else the latest published, else the draft. */
export function previewVersion(
  workflow: Pick<WorkflowView, "latest_version" | "draft">,
  version: string | null,
): string | null {
  if (version !== null) return version;
  if (workflow.latest_version > 0) return String(workflow.latest_version);
  return workflow.draft !== null ? "draft" : null;
}

/** An execution's spend, an estimate while a reservation is held or a charge went unreported. */
export function spendText(execution: WorkflowExecutionSummary): string {
  const { micro, estimated } = spendOf(
    execution.charged_micro_usd,
    execution.reserved_micro_usd,
    execution.unreported,
  );
  const amount = formatUsd(micro);
  return estimated ? `≈ ${amount}, estimated` : `${amount}, reported`;
}

/** An execution's wall time, or that it's still running. */
export function durationText(seconds: number | null): string {
  return seconds === null ? "still running" : formatDuration(seconds);
}
