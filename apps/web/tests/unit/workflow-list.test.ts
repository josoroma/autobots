/**
 * Pins the Workflows list's rules (WBLD-11, R-59): which tab holds a workflow (PRD-Studio WF-01),
 * which version a preview shows first and where it's read (PRD-Studio WF-03), and an execution's
 * spend and duration words, with an estimate said as one (PRD-Studio WF-04).
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  listWorkflowExecutions,
  previewWorkflowVersion,
  type WorkflowExecutionSummary,
} from "@autobots/api-client";

import { load, readOf, type Read } from "../../lib/load.ts";
import {
  durationText,
  inWorkflowTab,
  previewVersion,
  spendText,
  WORKFLOW_TAB_IDS,
  WORKFLOW_TABS,
} from "../../lib/workflows/list.ts";

const draft = { graph: { nodes: [] }, saved_at: "2026-11-15T12:00:00Z" };

const published = {
  latest_version: 2,
  draft: null,
  versions: [{ version: 1 }, { version: 2 }],
};
const drafted = { latest_version: 0, draft, versions: [] };
const both = { latest_version: 1, draft, versions: [{ version: 1 }] };
const neither = { latest_version: 0, draft: null, versions: [] };

const execution = (
  changes: Partial<WorkflowExecutionSummary>,
): WorkflowExecutionSummary => ({
  id: "x-1",
  run_id: "r-1",
  version: 1,
  status: "succeeded",
  started_at: "2026-11-15T12:00:00Z",
  charged_micro_usd: 0,
  reserved_micro_usd: 0,
  unreported: false,
  duration_seconds: 65,
  ...changes,
});

test("the tabs are All, Published and Drafts, and each holds its workflows", () => {
  assert.deepEqual(
    WORKFLOW_TABS.map((tab) => [tab.id, tab.label]),
    [
      ["all", "All"],
      ["published", "Published"],
      ["drafts", "Drafts"],
    ],
  );
  assert.deepEqual(WORKFLOW_TAB_IDS, ["all", "published", "drafts"]);
  assert.deepEqual(
    [published, drafted, both, neither].map((workflow) =>
      WORKFLOW_TAB_IDS.map((tab) => inWorkflowTab(workflow, tab)),
    ),
    [
      [true, true, false],
      [true, false, true],
      [true, true, true],
      [true, false, false],
    ],
  );
});

test("a preview shows the version asked for, else the latest published, else the draft", () => {
  assert.equal(previewVersion(published, "1"), "1");
  assert.equal(previewVersion(published, null), "2");
  assert.equal(previewVersion(both, null), "1");
  assert.equal(previewVersion(drafted, null), "draft");
  assert.equal(previewVersion(neither, null), null);
});

/** The URL the browser asks for with this read. */
async function urlOf(source: Read<unknown>): Promise<string> {
  const asked: string[] = [];
  await load(source, {
    fetch: async (input) => {
      asked.push(String(input));
      return new Response("{}", { status: 503 });
    },
  });
  return asked[0] ?? "";
}

test("a preview's and the executions' reads name the workflow", async () => {
  assert.equal(
    await urlOf(readOf(listWorkflowExecutions, "w 1")),
    "/api/v1/workflows/w%201/executions",
  );
  assert.equal(
    await urlOf(readOf(previewWorkflowVersion, "w 1", { version: "draft" })),
    "/api/v1/workflows/w%201/preview?version=draft",
  );
  assert.equal(
    await urlOf(readOf(previewWorkflowVersion, "w-1", { version: "2" })),
    "/api/v1/workflows/w-1/preview?version=2",
  );
});

test("an execution's spend is an estimate while a reservation is held or a charge went unreported", () => {
  assert.equal(
    spendText(execution({ charged_micro_usd: 250_000 })),
    "US$0.25, reported",
  );
  assert.equal(
    spendText(
      execution({ charged_micro_usd: 100_000, reserved_micro_usd: 150_000 }),
    ),
    "≈ US$0.25, estimated",
  );
  assert.equal(
    spendText(execution({ unreported: true })),
    "≈ US$0.00, estimated",
  );
});

test("an execution still running says so instead of a duration", () => {
  assert.equal(durationText(null), "still running");
  assert.equal(durationText(65), "1m 05s");
  assert.equal(durationText(7), "7s");
});
