/**
 * The approval gate's words (WTAP-01, WTAP-09): who asked, what was in scope and which policy held
 * the call, as stored with each request (Decision 0015), who decided it, and what a decision did,
 * from the status the service returned rather than the button pressed. Pure and JSX-free, so
 * `node --test` covers it.
 */
import type { ApprovalResult, ApprovalView } from "@autobots/api-client";

import type { Decision } from "./approval-shortcut.ts";
import { changedChoice, withHeld } from "./submit.ts";
import type { Submitted } from "./use-submit.ts";

/** Said for a field stored only with newer requests. */
export const NOT_RECORDED =
  "not recorded, as this request is older than that record.";

/** A request too long to show whole can only be rejected (PRD-Studio AP-03). */
export const TOO_LARGE =
  "This request is too long to show whole, so it can't be approved. Reject it, or have it made smaller.";

/** Said when an armed shortcut lapses (PRD-Studio AP-04). */
export const NOTHING_DECIDED = "Nothing was decided.";

/** A decision refusal's words, by the service's code. */
export const DECISION_REFUSALS: Readonly<Record<string, string>> = {
  owner_required: "Only the workspace owner can decide.",
  approval_expired: "This request expired, so it was not approved.",
  approval_mismatch: "The request changed. Reload and review it again.",
  approval_too_large: TOO_LARGE,
  approval_already_decided: "This request was already decided.",
  approval_run_not_waiting:
    "The run isn't waiting for this decision. Resume it first.",
};

const OUTCOME: Readonly<Record<string, string>> = {
  approved: "Approved",
  rejected: "Rejected",
  expired: "Expired, so it was not approved",
  withdrawn: "Withdrawn",
};

// What a decision did, from the status the service returned, not the button pressed.
const DECIDED: Readonly<Record<string, string>> = {
  approved: "Approved. Only this exact request is released.",
  rejected: "Rejected. The run can replan or fail, and this request won't run.",
};

// Each decision in the words of its button, for a message that names it.
const BUTTONS: Readonly<Record<Decision, string>> = {
  approve: "Approve",
  reject: "Reject",
};

const CHORDS: Readonly<Record<Decision, string>> = {
  approve: "⌘↵",
  reject: "⌘⌫",
};

/** A request's outcome in words. A status without words stays as sent. */
export function outcomeText(status: string): string {
  return OUTCOME[status] ?? status;
}

/** What one decision did, or why it didn't (Decision 0027 D2 for a held one). */
export function decisionText(result: Submitted<ApprovalResult>): string {
  if (result.outcome === "accepted" && result.value !== null) {
    const status = result.value.status;
    return DECIDED[status] ?? `${outcomeText(status)}.`;
  }
  if (result.outcome === "changed") {
    const held = result.heldChoice;
    return changedChoice(
      held === "approve" || held === "reject" ? BUTTONS[held] : (held ?? ""),
    );
  }
  if (result.outcome === "unknown") {
    return "The reply was lost, so this may have been decided. Deciding again won't apply it twice.";
  }
  return withHeld(
    DECISION_REFUSALS[result.refusal?.code ?? ""] ??
      "That decision couldn't be saved.",
    result.held,
  );
}

/** Said after a first press, while the shortcut is armed (PRD-Studio AP-04). */
export function armedText(
  decision: Decision,
  approval: Pick<ApprovalView, "tool_id" | "tool_version">,
): string {
  return `Press ${CHORDS[decision]} again within 2 seconds to ${decision} ${approval.tool_id}, version ${approval.tool_version}.`;
}

/** Who started the run, and which agent proposed the call (Decision 0015). */
export function requesterText(
  approval: Pick<ApprovalView, "requester">,
): string {
  const requester = approval.requester;
  if (requester === null) {
    return NOT_RECORDED;
  }
  const person =
    requester.person_id === null
      ? "no person is recorded for this run"
      : requester.person_is_viewer
        ? "you started this run"
        : `member ${requester.person_id} started this run`;
  const agent =
    requester.agent === "coordinator"
      ? "the coordinator proposed it"
      : `Expert ${requester.expert_name === null ? requester.expert_id : `"${requester.expert_name}"`}, version ${requester.expert_version}, proposed it`;
  return `${person}, and ${agent}.`;
}

/** The tools, by name, and the paths in scope when the call was proposed. */
export function scopeText(
  approval: Pick<ApprovalView, "scope_snapshot">,
): string {
  const scope = approval.scope_snapshot;
  if (scope === null) {
    return NOT_RECORDED;
  }
  const tools = Object.entries(scope.tools)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([name, version]) => `${name} version ${version}`);
  const paths = scope.paths.length === 0 ? "none" : scope.paths.join(", ");
  return `tools ${tools.length === 0 ? "none" : tools.join(", ")}; paths ${paths}.`;
}

/** The policy version that held the call, and its rule in words. */
export function policyText(
  approval: Pick<ApprovalView, "policy_version" | "policy_rule">,
): string {
  if (approval.policy_version === null) {
    return NOT_RECORDED;
  }
  const rule =
    approval.policy_rule === null
      ? ""
      : `, rule ${approval.policy_rule.replaceAll("_", " ")}`;
  return `${approval.policy_version}${rule}.`;
}

/** A decided request's outcome, who decided it and when, in the viewer's locale. */
export function decidedText(
  approval: Pick<
    ApprovalView,
    "status" | "decided_by" | "decided_by_name" | "decided_at"
  >,
): string {
  const outcome = outcomeText(approval.status);
  const who =
    approval.decided_by === "you"
      ? " by you"
      : approval.decided_by === "member"
        ? ` by ${approval.decided_by_name ?? "a workspace member"}`
        : "";
  const when =
    approval.decided_at === null
      ? ""
      : ` at ${new Date(approval.decided_at).toLocaleString()}`;
  return `${outcome}${who}${when}.`;
}
