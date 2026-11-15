/**
 * Pins the approval gate's words (WTAP-09, R-45): who asked (Decision 0015), the scope and policy
 * stored with a request, who decided it, a decision's outcome from the status the service returned,
 * and the two-press shortcut's announcement (PRD-Studio AP-04).
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import type { ApprovalResult } from "@autobots/api-client";

import {
  armedText,
  decidedText,
  decisionText,
  DECISION_REFUSALS,
  NOT_RECORDED,
  outcomeText,
  policyText,
  requesterText,
  scopeText,
  TOO_LARGE,
} from "../../lib/approval-text.ts";
import { HELD_NOTE } from "../../lib/submit.ts";
import type { Submitted } from "../../lib/use-submit.ts";

const expert = {
  agent: "expert" as const,
  expert_id: "e-1",
  expert_name: "Mail sender",
  expert_version: 2,
  person_id: "p-1",
  person_is_viewer: true,
};

function submitted(
  over: Partial<Submitted<ApprovalResult>>,
): Submitted<ApprovalResult> {
  return {
    outcome: "accepted",
    value: null,
    refusal: null,
    status: null,
    retried: false,
    held: false,
    heldChoice: null,
    ...over,
  };
}

function result(status: string): ApprovalResult {
  return { approval_id: "a", replayed: false, schema_version: 1, status };
}

test("a request saved before the requester was recorded says so", () => {
  assert.equal(requesterText({ requester: null }), NOT_RECORDED);
  assert.equal(
    NOT_RECORDED,
    "not recorded, as this request is older than that record.",
  );
});

test("the requester names the viewer, a member or no person, and the agent that proposed the call", () => {
  assert.equal(
    requesterText({ requester: expert }),
    'you started this run, and Expert "Mail sender", version 2, proposed it.',
  );
  assert.equal(
    requesterText({
      requester: { ...expert, person_is_viewer: false, expert_name: null },
    }),
    "member p-1 started this run, and Expert e-1, version 2, proposed it.",
  );
  assert.equal(
    requesterText({
      requester: { ...expert, agent: "coordinator", person_id: null },
    }),
    "no person is recorded for this run, and the coordinator proposed it.",
  );
});

test("the scope lists its tools by name with their versions, and its paths", () => {
  assert.equal(scopeText({ scope_snapshot: null }), NOT_RECORDED);
  assert.equal(
    scopeText({
      scope_snapshot: {
        tools: { mock_send: 1, file_read: 3 },
        paths: ["docs", "src"],
      },
    }),
    "tools file_read version 3, mock_send version 1; paths docs, src.",
  );
  assert.equal(
    scopeText({ scope_snapshot: { tools: {}, paths: [] } }),
    "tools none; paths none.",
  );
});

test("the policy version names its rule in words, when one is stored", () => {
  assert.equal(
    policyText({ policy_version: null, policy_rule: null }),
    NOT_RECORDED,
  );
  assert.equal(
    policyText({
      policy_version: "approval-policy/2",
      policy_rule: "consequential_external_write",
    }),
    "approval-policy/2, rule consequential external write.",
  );
  assert.equal(
    policyText({ policy_version: "approval-policy/1", policy_rule: null }),
    "approval-policy/1.",
  );
});

test("an outcome reads in words, and a status without words stays as sent", () => {
  assert.equal(outcomeText("approved"), "Approved");
  assert.equal(outcomeText("rejected"), "Rejected");
  assert.equal(outcomeText("expired"), "Expired, so it was not approved");
  assert.equal(outcomeText("withdrawn"), "Withdrawn");
  assert.equal(outcomeText("superseded"), "superseded");
});

test("a decided request says who decided it, and when", () => {
  const at = "2026-11-15T10:00:00Z";
  const when = new Date(at).toLocaleString();
  const decided = {
    status: "approved",
    decided_by: "you" as const,
    decided_by_name: null,
    decided_at: at,
  };
  assert.equal(decidedText(decided), `Approved by you at ${when}.`);
  assert.equal(
    decidedText({
      ...decided,
      status: "rejected",
      decided_by: "member",
      decided_by_name: "Ana",
    }),
    `Rejected by Ana at ${when}.`,
  );
  assert.equal(
    decidedText({ ...decided, decided_by: "member" }),
    `Approved by a workspace member at ${when}.`,
  );
  assert.equal(
    decidedText({
      ...decided,
      status: "expired",
      decided_by: null,
      decided_at: null,
    }),
    "Expired, so it was not approved.",
  );
});

test("a decision's words come from the status the service returned, not the button pressed", () => {
  const accepted = (status: string) =>
    decisionText(submitted({ value: result(status) }));
  assert.equal(
    accepted("approved"),
    "Approved. Only this exact request is released.",
  );
  assert.equal(
    accepted("rejected"),
    "Rejected. The run can replan or fail, and this request won't run.",
  );
  assert.equal(accepted("expired"), "Expired, so it was not approved.");
  assert.equal(accepted("superseded"), "superseded.");
});

test("another choice while one is held sends nothing, and names the held one by its button", () => {
  const changed = (heldChoice: string | null) =>
    decisionText(submitted({ outcome: "changed", held: true, heldChoice }));
  assert.match(
    changed("approve"),
    /^Nothing was sent\. Your first choice, "Approve"/,
  );
  assert.match(changed("reject"), /Your first choice, "Reject"/);
  assert.match(
    changed("approve"),
    /Reload to see it before choosing differently\.$/,
  );
});

test("a lost reply may have decided, and deciding again won't apply it twice", () => {
  assert.equal(
    decisionText(submitted({ outcome: "unknown" })),
    "The reply was lost, so this may have been decided. Deciding again won't apply it twice.",
  );
});

test("a refusal reads in this screen's words, with the held note when it answered a resend", () => {
  const refused = (code: string, held = false) =>
    decisionText(
      submitted({
        outcome: "refused",
        refusal: { code, message: "Arranged." },
        status: 409,
        held,
      }),
    );
  assert.equal(
    refused("approval_expired"),
    "This request expired, so it was not approved.",
  );
  assert.equal(refused("approval_too_large"), TOO_LARGE);
  assert.equal(
    refused("approval_already_decided"),
    DECISION_REFUSALS.approval_already_decided,
  );
  assert.equal(refused("arranged_code"), "That decision couldn't be saved.");
  assert.equal(
    refused("owner_required", true),
    `Only the workspace owner can decide. ${HELD_NOTE}`,
  );
});

test("the first press names the chord to press again, the decision and the request", () => {
  const request = { tool_id: "mock_send", tool_version: 1 };
  assert.equal(
    armedText("approve", request),
    "Press ⌘↵ again within 2 seconds to approve mock_send, version 1.",
  );
  assert.equal(
    armedText("reject", request),
    "Press ⌘⌫ again within 2 seconds to reject mock_send, version 1.",
  );
});
