/**
 * Pins the Expert editor's grant rules (WBLD-10, R-59): what an Expert may be granted from the
 * catalog (PRD-Tool-Catalog TC-06, TS-04), whole groups read once with their unavailable tools, the
 * explicit list a save records and its sentence, and the two-field update when one tool of a whole
 * group is unchecked.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import type { ToolDescriptor } from "@autobots/api-client";

import {
  expansion,
  expansionText,
  grantable,
  grantGroups,
  groupGrantLabel,
  groupLocked,
  toolGrant,
  toolGrantLabel,
  unavailableText,
  withGroup,
  withTool,
  type GrantCatalog,
  type GrantTool,
} from "../../lib/experts/grants.ts";

const tool = (
  tool_id: string,
  group: ToolDescriptor["group"],
  changes: Partial<GrantTool> = {},
): GrantTool => ({
  tool_id,
  group,
  title: tool_id,
  approval: "never",
  availability: "available",
  availability_reason: null,
  key_requirement: null,
  grantable_to: ["expert", "goal"],
  ...changes,
});

const catalog: GrantCatalog<GrantTool> = {
  groups: [
    { group: "general", title: "General" },
    { group: "files", title: "Files" },
    { group: "connectors", title: "Connectors" },
    { group: "delegation", title: "Delegation" },
  ],
  tools: [
    tool("calculate", "general"),
    tool("read_csv", "files"),
    tool("save_artifact", "files"),
    tool("create_github_issue", "connectors", { availability: "key_missing" }),
    tool("github_read_file", "connectors"),
    tool("delegate", "delegation", { grantable_to: ["coordinator"] }),
  ],
};

const draft = (tools: string[] = [], groups: string[] = []) => ({
  tools,
  groups,
  purpose: "kept",
});

test("only tools grantable to an Expert are offered, and nothing before the catalog is read", () => {
  assert.deepEqual(
    grantable(catalog).map((item) => item.tool_id),
    [
      "calculate",
      "read_csv",
      "save_artifact",
      "create_github_issue",
      "github_read_file",
    ],
  );
  assert.deepEqual(grantable(null), []);
});

test("each group with grantable tools is read once, with whether it holds an unavailable one", () => {
  const groups = grantGroups(catalog);
  assert.deepEqual(
    groups.map((group) => [group.group, group.tools.length, group.blocked]),
    [
      ["general", 1, false],
      ["files", 2, false],
      ["connectors", 2, true],
    ],
  );
  const [general, files, connectors] = groups;
  assert.ok(general && files && connectors);
  assert.equal(groupGrantLabel(general), "General group (1 tool)");
  assert.equal(groupGrantLabel(files), "Files group (2 tools)");
  assert.equal(
    groupGrantLabel(connectors),
    "Connectors group (2 tools), includes an unavailable tool",
  );
});

test("a blocked group can be unchecked but not checked", () => {
  const [, files, connectors] = grantGroups(catalog);
  assert.ok(files && connectors);
  assert.equal(groupLocked(connectors, false), true);
  assert.equal(groupLocked(connectors, true), false);
  assert.equal(groupLocked(files, false), false);
});

test("the expansion lists the tools named, then each whole group's tools, once each", () => {
  assert.deepEqual(
    expansion(catalog, draft(["save_artifact", "calculate"], ["files"])),
    ["save_artifact", "calculate", "read_csv"],
  );
  assert.deepEqual(expansion(null, draft(["calculate"], ["files"])), [
    "calculate",
  ]);
  assert.deepEqual(expansion(catalog, draft()), []);
});

test("the expansion sentence names the groups only when there are some", () => {
  assert.equal(expansionText([], []), "This version grants no tools.");
  assert.equal(
    expansionText(["calculate"], []),
    "This version grants: calculate.",
  );
  assert.equal(
    expansionText(["calculate", "read_csv", "save_artifact"], ["files"]),
    "This version grants: calculate, read_csv, save_artifact, from the group files and the tools named.",
  );
  assert.equal(
    expansionText(["read_csv", "github_read_file"], ["files", "connectors"]),
    "This version grants: read_csv, github_read_file, from the groups files, connectors and the tools named.",
  );
});

test("checking a group adds it, and unchecking removes only it", () => {
  assert.deepEqual(
    withGroup(draft([], ["general"]), "files", true),
    draft([], ["general", "files"]),
  );
  assert.deepEqual(
    withGroup(draft([], ["general", "files"]), "general", false),
    draft([], ["files"]),
  );
});

test("unchecking one tool of a whole group means the group isn't whole", () => {
  const files = { tool_id: "read_csv", group: "files" } as const;
  assert.deepEqual(
    withTool(draft(["calculate"], ["files"]), files, true),
    draft(["calculate", "read_csv"], ["files"]),
  );
  assert.deepEqual(
    withTool(
      draft(["calculate", "read_csv"], ["files", "general"]),
      files,
      false,
    ),
    draft(["calculate"], ["general"]),
  );
});

test("a tool is checked when named or granted with its group, and an unavailable one can only be unchecked", () => {
  const issue = tool("create_github_issue", "connectors", {
    availability: "key_missing",
  });
  const csv = tool("read_csv", "files");
  assert.deepEqual(toolGrant(csv, draft()), {
    checked: false,
    unavailable: false,
    locked: false,
  });
  assert.deepEqual(toolGrant(csv, draft([], ["files"])), {
    checked: true,
    unavailable: false,
    locked: false,
  });
  assert.deepEqual(toolGrant(issue, draft()), {
    checked: false,
    unavailable: true,
    locked: true,
  });
  assert.deepEqual(toolGrant(issue, draft(["create_github_issue"])), {
    checked: true,
    unavailable: true,
    locked: false,
  });
});

test("a tool's label says when it waits for approval, and an unavailable one says why", () => {
  assert.equal(
    toolGrantLabel({ title: "Calculate", approval: "never" }),
    "Calculate",
  );
  assert.equal(
    toolGrantLabel({ title: "Create issue", approval: "always" }),
    "Create issue, after approval",
  );
  assert.equal(
    toolGrantLabel({ title: "Browse", approval: "by_action" }),
    "Browse",
  );
  assert.equal(
    unavailableText({
      availability: "disabled_by_policy",
      availability_reason: null,
      key_requirement: null,
    }),
    "Unavailable: disabled by policy",
  );
  assert.equal(
    unavailableText({
      availability: "not_qualified",
      availability_reason: null,
      key_requirement: null,
    }),
    "Unavailable: not qualified. Waits for its provider's qualification.",
  );
});
