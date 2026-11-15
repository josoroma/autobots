/**
 * Pins the search palette's keyboard and status (PRD-Studio SR-01, Decision 0022 D3, WCMP-10): ⌘K
 * or Ctrl+K opens it, the arrows wrap around the results, and the status line says what a search
 * found, or why it failed, never that nothing matches.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import { moveActive } from "../../lib/keyboard.ts";
import { searchStatusText } from "../../lib/search-status.ts";
import { SEARCH_SHORTCUT, SHORTCUTS } from "../../lib/shortcuts.ts";

const isSearchShortcut = SEARCH_SHORTCUT.matches;

const PRESS = { key: "k", metaKey: false, ctrlKey: false, altKey: false };

test("⌘K or Ctrl+K opens search, and Alt or another key doesn't", () => {
  assert.equal(isSearchShortcut({ ...PRESS, metaKey: true }), true);
  assert.equal(isSearchShortcut({ ...PRESS, ctrlKey: true }), true);
  assert.equal(isSearchShortcut({ ...PRESS, metaKey: true, key: "K" }), true);
  assert.equal(isSearchShortcut(PRESS), false);
  assert.equal(
    isSearchShortcut({ ...PRESS, metaKey: true, altKey: true }),
    false,
  );
  assert.equal(isSearchShortcut({ ...PRESS, metaKey: true, key: "j" }), false);
});

test("the one ⌘K definition is the one Settings → Keyboard lists, with its hint and aria name", () => {
  const anywhere = SHORTCUTS.find((group) => group.where === "Anywhere");
  assert.ok(anywhere?.shortcuts.includes(SEARCH_SHORTCUT));
  assert.equal(SEARCH_SHORTCUT.keys.join(""), "⌘K");
  assert.equal(SEARCH_SHORTCUT.aria, "Meta+K Control+K");
});

test("the arrows move through the results and wrap at both ends", () => {
  assert.equal(moveActive(0, "ArrowDown", 3), 1);
  assert.equal(moveActive(2, "ArrowDown", 3), 0);
  assert.equal(moveActive(0, "ArrowUp", 3), 2);
  assert.equal(moveActive(1, "ArrowUp", 3), 0);
  assert.equal(moveActive(1, "Enter", 3), 1);
  assert.equal(moveActive(0, "ArrowDown", 0), 0);
});

test("the status line says how to start, that it's searching, what was found, or why it failed", () => {
  const ready = { idle: false, searching: false, failure: null, count: 0 };
  assert.equal(
    searchStatusText({ ...ready, idle: true }),
    "Type to search. ↑ ↓ to move, ↵ to open, Esc to close.",
  );
  assert.equal(searchStatusText({ ...ready, searching: true }), "Searching.");
  assert.equal(searchStatusText(ready), "Nothing in this workspace matches.");
  assert.equal(searchStatusText({ ...ready, count: 1 }), "1 result.");
  assert.equal(searchStatusText({ ...ready, count: 12 }), "12 results.");
  assert.equal(
    searchStatusText({
      ...ready,
      failure: { kind: "unavailable", status: 503 },
    }),
    "Search results can't be read right now. Check that the local services are running, then try again.",
  );
  assert.equal(
    searchStatusText({
      ...ready,
      failure: { kind: "out_of_date", schema: "SearchResults", path: "x" },
    }),
    "This page and the local service disagree. Reload after updating.",
  );
});
