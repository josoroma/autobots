/**
 * Pins the Experts list's classification and card words (WBLD-12, R-59): whether an Expert can
 * change something outside, which stays unknown until the catalog is read (PRD-Studio EX-02, EX-03),
 * each filter's members, and the executor, runs, approval and tool lines of a card.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import type { ExpertView } from "@autobots/api-client";

import {
  approvalNote,
  browseDomainsLine,
  classify,
  EXPERT_FILTERS,
  executorLine,
  inExpertFilter,
  initialOf,
  runsLine,
  toolChips,
  type CatalogTools,
} from "../../lib/experts/card.ts";

const expert = (
  name: string,
  config: ExpertView["versions"][number]["config"] = {},
  changes: Partial<ExpertView> = {},
): ExpertView => ({
  id: `id-${name}`,
  name,
  latest_version: 1,
  last_run_at: null,
  run_count: 0,
  schema_version: 1,
  versions: [{ version: 1, config }],
  ...changes,
});

const catalog: CatalogTools = new Map([
  ["calculate", { operation_class: "pure", approval: "never" }],
  ["read_csv", { operation_class: "read_only", approval: "never" }],
  [
    "create_github_issue",
    { operation_class: "consequential_external_write", approval: "always" },
  ],
  [
    "github_open_pull_request",
    { operation_class: "consequential_external_write", approval: "always" },
  ],
  // Decision 0035 Y2: browse_goal waits for a person only while YOLO is off.
  ["browse_goal", { operation_class: "read_only", approval: "unless_yolo" }],
]);

const triager = expert("Issue triager", {
  tools: ["read_csv", "create_github_issue"],
});
const calculator = expert("Calculator", { tools: ["calculate"] });
const empty = expert("Empty");

test("an Expert can change things outside when its latest version grants such a tool", () => {
  const items = classify([triager, calculator, empty], catalog);
  assert.deepEqual(
    items.map((item) => [item.expert.name, item.outside]),
    [
      ["Issue triager", true],
      ["Calculator", false],
      ["Empty", false],
    ],
  );
  const older = expert(
    "Older",
    { tools: ["calculate"] },
    {
      versions: [
        { version: 1, config: { tools: ["create_github_issue"] } },
        { version: 2, config: { tools: ["calculate"] } },
      ],
    },
  );
  assert.equal(classify([older], catalog)[0]?.outside, false);
});

test("before the catalog is read, no Expert is called read only", () => {
  const items = classify([triager, calculator], null);
  assert.deepEqual(
    items.map((item) => item.outside),
    [null, null],
  );
  for (const item of items) {
    assert.equal(inExpertFilter(item, "all"), true);
    assert.equal(inExpertFilter(item, "outside"), false);
    assert.equal(inExpertFilter(item, "read_only"), false);
  }
});

test("each filter holds its class, and All holds every Expert", () => {
  const [outside, readOnly] = classify([triager, calculator], catalog);
  assert.ok(outside && readOnly);
  assert.deepEqual(
    EXPERT_FILTERS.map(([id]) => [
      inExpertFilter(outside, id),
      inExpertFilter(readOnly, id),
    ]),
    [
      [true, true],
      [true, false],
      [false, true],
    ],
  );
  assert.deepEqual(
    EXPERT_FILTERS.map(([, label]) => label),
    ["All", "Can change things outside", "Read only"],
  );
});

test("a card's executor line names the profile, or the workspace default", () => {
  assert.equal(
    executorLine(calculator),
    "executor · Workspace default · version 1",
  );
  assert.equal(
    executorLine(
      expert(
        "Watcher",
        { role_bindings: { executor: "openrouter_terra" } },
        { latest_version: 3 },
      ),
    ),
    "executor · Terra · version 3",
  );
});

test("a card's runs line counts runs and says when the last one was", () => {
  const now = Date.parse("2026-11-15T12:00:00Z");
  assert.equal(runsLine(calculator, now), "No runs yet");
  assert.equal(runsLine(expert("One", {}, { run_count: 1 }), now), "1 run");
  assert.equal(
    runsLine(
      expert(
        "Three",
        {},
        { run_count: 3, last_run_at: "2026-11-15T11:55:00Z" },
      ),
      now,
    ),
    "3 runs · last run 5 minutes ago",
  );
});

test("the approval note names what one always-approved tool decides on", () => {
  assert.equal(
    approvalNote(["read_csv", "create_github_issue"], catalog),
    "Approval on every issue",
  );
  assert.equal(
    approvalNote(["github_open_pull_request"], catalog),
    "Approval on every pull request",
  );
  assert.equal(
    approvalNote(["browse_goal"], catalog),
    "Approval on every call, while YOLO is off",
  );
  assert.equal(
    approvalNote(["create_github_issue", "browse_goal"], catalog),
    "Approval on every call to these tools",
  );
  assert.equal(approvalNote(["calculate"], catalog), null);
  assert.equal(approvalNote(["create_github_issue"], null), null);
});

test("a card shows four tools, then how many more, then its groups", () => {
  assert.deepEqual(toolChips({}), ["no tools"]);
  assert.deepEqual(toolChips({ tools: ["a", "b"] }), ["a", "b"]);
  assert.deepEqual(toolChips({ tools: ["a", "b", "c", "d", "e", "f"] }), [
    "a",
    "b",
    "c",
    "d",
    "+2",
  ]);
  assert.deepEqual(
    toolChips({ tools: ["a"], tool_groups: ["files", "general"] }),
    ["a", "groups: files, general"],
  );
  assert.deepEqual(toolChips({ tool_groups: ["files"] }), ["groups: files"]);
});

test("an Expert's tile shows its name's first letter", () => {
  assert.equal(initialOf("  market watcher"), "M");
  assert.equal(initialOf(""), "");
});

test("an Expert that browses says where, or that it can't until its domains are listed", () => {
  assert.equal(
    browseDomainsLine({ tools: ["browse_goal", "save_artifact"] }),
    "No browse domains yet, so it can't browse",
  );
  assert.equal(
    browseDomainsLine({
      tools: ["browse_goal"],
      browse_domains: ["youtube.com", "ytimg.com"],
    }),
    "Browses youtube.com, ytimg.com",
  );
  assert.equal(
    browseDomainsLine({
      tools: ["browse_goal"],
      browse_domains: ["a.test"],
      browser: "stealth",
    }),
    "Browses a.test, on the stealth browser",
  );
  assert.equal(
    browseDomainsLine({ tools: ["save_artifact"], browse_domains: ["a.test"] }),
    null,
  );
});
