/**
 * Pins the Tools page's filters (WTAP-08, R-59): read from the URL so a view can be linked
 * (PRD-Tool-Catalog TS-01), matched on group, availability, provider and text, grouped once in the
 * catalog's order, and the providers the filter offers.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import type { ToolDescriptor } from "@autobots/api-client";

import {
  filterTools,
  groupTools,
  providersOf,
  readToolFilters,
  type FilterTool,
} from "../../lib/tools/filters.ts";

const tool = (
  tool_id: string,
  group: ToolDescriptor["group"],
  changes: Partial<FilterTool> = {},
): FilterTool => ({
  tool_id,
  group,
  title: tool_id,
  description: "",
  availability: "available",
  provider: "autobots",
  ...changes,
});

const tools: readonly FilterTool[] = [
  tool("calculate", "general", {
    title: "Calculate",
    description: "Sums numbers",
  }),
  tool("read_csv", "files", { title: "Read CSV" }),
  tool("search_web", "web_search", {
    provider: "tavily",
    availability: "key_missing",
  }),
  tool("save_artifact", "files", { description: "Keeps a file for later" }),
  tool("browse_goal", "browsing", { availability: "disabled_by_policy" }),
];
const ids = (list: readonly FilterTool[]) => list.map((item) => item.tool_id);

test("the filters come from the URL, and a missing one matches everything", () => {
  assert.deepEqual(readToolFilters(new URLSearchParams("")), {
    group: "",
    availability: "",
    provider: "",
    search: "",
  });
  assert.deepEqual(
    readToolFilters(
      new URLSearchParams(
        "group=files&availability=available&provider=tavily&q=+CSV+",
      ),
    ),
    {
      group: "files",
      availability: "available",
      provider: "tavily",
      search: " CSV ",
    },
  );
});

test("each filter narrows the list, and the text matches title, ID or description", () => {
  const none = { group: "", availability: "", provider: "", search: "" };
  assert.deepEqual(ids(filterTools(tools, none)), ids(tools));
  assert.deepEqual(ids(filterTools(tools, { ...none, group: "files" })), [
    "read_csv",
    "save_artifact",
  ]);
  assert.deepEqual(
    ids(filterTools(tools, { ...none, availability: "disabled_by_policy" })),
    ["browse_goal"],
  );
  assert.deepEqual(ids(filterTools(tools, { ...none, provider: "tavily" })), [
    "search_web",
  ]);
  assert.deepEqual(ids(filterTools(tools, { ...none, search: " sums " })), [
    "calculate",
  ]);
  assert.deepEqual(ids(filterTools(tools, { ...none, search: "csv" })), [
    "read_csv",
  ]);
  assert.deepEqual(ids(filterTools(tools, { ...none, search: "later" })), [
    "save_artifact",
  ]);
  assert.deepEqual(
    ids(filterTools(tools, { ...none, group: "files", search: "csv" })),
    ["read_csv"],
  );
});

test("tools are grouped once, in the catalog's order, and a group with none shown is left out", () => {
  const groups = [
    { group: "planning", title: "Planning" },
    { group: "files", title: "Files" },
    { group: "general", title: "General" },
    { group: "web_search", title: "Web search" },
  ] as const;
  const grouped = groupTools(groups, tools);
  assert.deepEqual(
    grouped.map((item) => [item.group.group, ids(item.tools)]),
    [
      ["files", ["read_csv", "save_artifact"]],
      ["general", ["calculate"]],
      ["web_search", ["search_web"]],
    ],
  );
  assert.deepEqual(groupTools(groups, []), []);
});

test("the provider filter offers each provider once, in the catalog's order", () => {
  assert.deepEqual(providersOf(tools), ["autobots", "tavily"]);
  assert.deepEqual(providersOf([]), []);
});
