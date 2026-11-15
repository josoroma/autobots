/**
 * Pins the list filter the Experts and Workflows screens share (WBLD-09, R-59): one tab and one
 * search matched by name, each tab's count, a tab read from a URL, and the URLs the lists and the
 * tool catalog build.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  filterList,
  matchesSearch,
  parseTab,
  searchNeedle,
  tabCounts,
  withParams,
} from "../../lib/list-filter.ts";

type Tab = "all" | "even" | "odd";
const TABS: readonly Tab[] = ["all", "even", "odd"];

interface Item {
  name: string;
  n: number;
}
const items: readonly Item[] = [
  { name: "One", n: 1 },
  { name: "Two", n: 2 },
  { name: "Three", n: 3 },
];
const inTab = (item: Item, tab: Tab): boolean =>
  tab === "all" || (tab === "even") === (item.n % 2 === 0);
const nameOf = (item: Item): string => item.name;
const names = (list: readonly Item[]): string[] => list.map(nameOf);

test("a search is trimmed and lower-cased, and an empty one matches every name", () => {
  assert.equal(searchNeedle("  BrIef "), "brief");
  assert.equal(matchesSearch("Brief writer", searchNeedle("brief")), true);
  assert.equal(matchesSearch("Brief writer", "writ"), true);
  assert.equal(matchesSearch("Brief writer", "market"), false);
  assert.equal(matchesSearch("Anything", ""), true);
});

test("a tab and a search both narrow the list, and its order stays", () => {
  assert.deepEqual(
    names(filterList(items, { tab: "all", search: "" }, inTab, nameOf)),
    ["One", "Two", "Three"],
  );
  assert.deepEqual(
    names(filterList(items, { tab: "odd", search: "" }, inTab, nameOf)),
    ["One", "Three"],
  );
  assert.deepEqual(
    names(filterList(items, { tab: "odd", search: " th " }, inTab, nameOf)),
    ["Three"],
  );
  assert.deepEqual(
    names(filterList(items, { tab: "even", search: "th" }, inTab, nameOf)),
    [],
  );
});

test("each tab counts what it holds, whatever the search", () => {
  const counts = tabCounts(items, TABS, inTab);
  assert.deepEqual(
    [...counts],
    [
      ["all", 3],
      ["even", 1],
      ["odd", 2],
    ],
  );
  assert.deepEqual(
    [...tabCounts([], TABS, inTab)],
    [
      ["all", 0],
      ["even", 0],
      ["odd", 0],
    ],
  );
});

test("a missing or unknown tab reads as the fallback, so a URL can't name one that doesn't exist", () => {
  assert.equal(parseTab("odd", TABS, "all"), "odd");
  assert.equal(parseTab(null, TABS, "all"), "all");
  assert.equal(parseTab("", TABS, "all"), "all");
  assert.equal(parseTab("ODD", TABS, "all"), "all");
  assert.equal(parseTab("drafts", TABS, "all"), "all");
});

test("withParams sets and removes parameters, keeping the others in their order", () => {
  assert.equal(
    withParams("/workflows", "", { tab: "drafts" }),
    "/workflows?tab=drafts",
  );
  assert.equal(
    withParams("/workflows", "tab=drafts&q=x", { q: null }),
    "/workflows?tab=drafts",
  );
  assert.equal(
    withParams("/workflows", "tab=drafts", { tab: "" }),
    "/workflows",
  );
  assert.equal(
    withParams("/workflows", "tab=drafts", { tab: null }),
    "/workflows",
  );
  assert.equal(withParams("/x", "a=1&b=2", { a: "3" }), "/x?a=3&b=2");
  assert.equal(
    withParams("/tools", "group=files&q=calc", { tool: "calculate" }),
    "/tools?group=files&q=calc&tool=calculate",
  );
  assert.equal(
    withParams("/workflows", "workflow=w-1&version=2", {
      workflow: "w-2",
      version: null,
    }),
    "/workflows?workflow=w-2",
  );
  assert.equal(withParams("/w", "", { q: "a b&c" }), "/w?q=a+b%26c");
  assert.equal(withParams("/w", "q=x", {}), "/w?q=x");
});
