/**
 * The run page's view of a snapshot (R-49, WRUN-01): the counts and rules its regions show, and the
 * short texts they say, pinned to the page's words.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import { parseRunWorkspace, type RunWorkspace } from "@autobots/api-client";

import {
  artifactFacts,
  connectionText,
  expertModels,
  expertTools,
  planNote,
  taskProgress,
  toWorkspaceView,
  unmetText,
} from "../../lib/runs/workspace-view.ts";
import { snapshot } from "./run-connection-fakes.ts";

const RUN = "11111111-1111-4111-8111-111111111111";

function workspace(patch: Record<string, unknown> = {}): RunWorkspace {
  return parseRunWorkspace({ ...snapshot(RUN, 4), ...patch });
}

const binding = (role: string, profile: string) => ({
  role,
  profile,
  canonical_id: `vendor/${profile}`,
  wire_id: `vendor/${profile}`,
  source: null,
});

test("the charge form counts calls without a settled charge, and Usage counts every unknown", () => {
  const view = toWorkspaceView(
    workspace({
      outstanding: {
        uncertain_calls: 2,
        unknown_effects: 3,
        unreported_charges: 4,
      },
    }),
  );
  assert.equal(view.openCalls, 6);
  assert.equal(view.unsettled, 9);
  const settled = toWorkspaceView(workspace());
  assert.equal(settled.openCalls, 0);
  assert.equal(settled.unsettled, 0);
});

test("only a run waiting for an approval links to Approvals", () => {
  const waiting = workspace({
    run: { ...snapshot(RUN, 4, "waiting_approval").run },
  });
  assert.equal(toWorkspaceView(waiting).awaitsApproval, true);
  assert.equal(toWorkspaceView(workspace()).awaitsApproval, false);
});

test("a summarizer bound apart from the executor is called out", () => {
  const apart = workspace({
    role_map: [binding("executor", "terra"), binding("summarizer", "sol")],
  });
  const same = workspace({
    role_map: [binding("executor", "terra"), binding("summarizer", "terra")],
  });
  assert.equal(toWorkspaceView(apart).summarizerDiffers, true);
  assert.equal(toWorkspaceView(same).summarizerDiffers, false);
});

test("context is said in thousands of tokens, rounded", () => {
  const view = toWorkspaceView(
    workspace({
      budgets: {
        context_tokens: 131_500,
        max_output_tokens_per_call: 8,
        call_seconds: 1_800,
        active_seconds: 14_400,
        model_calls: 64,
        tool_dispatches: 96,
      },
    }),
  );
  assert.equal(view.contextThousands, 132);
});

test("each stream state reads as the page says it", () => {
  assert.equal(connectionText("loading"), "Loading");
  assert.equal(connectionText("live"), "Live");
  assert.equal(
    connectionText("reconnecting"),
    "Reconnecting. Showing the last known state.",
  );
  assert.equal(
    connectionText("ended"),
    "Finished. No more activity is expected.",
  );
});

test("an unmet requirement reads as words", () => {
  assert.equal(unmetText("artifact:report_md"), "artifact: report md");
  assert.equal(unmetText("criterion_one"), "criterion one");
});

test("an Expert's tools and models read as a list, or say there are none", () => {
  assert.equal(expertTools([]), "none");
  assert.equal(
    expertTools(["web_search", "calculate"]),
    "web_search, calculate",
  );
  assert.equal(expertModels({}), "the workspace setting");
  assert.equal(
    expertModels({ executor: "terra", summarizer: "sol" }),
    "executor: terra, summarizer: sol",
  );
});

test("a plan says its version and why it was revised", () => {
  assert.equal(planNote({ version: 1, revision_reason: null }), "Version 1");
  assert.equal(
    planNote({ version: 3, revision_reason: "a source moved" }),
    "Version 3, revised because: a source moved",
  );
});

test("a task says whether it's done, then its evidence", () => {
  assert.equal(
    taskProgress({ status: "open", evidence_summary: null }),
    "open",
  );
  assert.equal(
    taskProgress({ status: "complete", evidence_summary: "Cited r.md" }),
    "complete. Cited r.md",
  );
});

test("an artifact says its size and the start of its digest", () => {
  assert.equal(
    artifactFacts({ size_bytes: 120, sha256: "0123456789abcdef".repeat(4) }),
    "120 bytes, sha256 0123456789ab",
  );
});
