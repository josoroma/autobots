/**
 * Pins Settings → Keys & vars' words and fields (Decisions 0024 and 0025, PRD-Tool-Catalog PK-04 to
 * PK-08, WSYS-14): where each item comes from, its field's label and control, and what a save or a
 * removal says. settings-keys-and-vars.spec.ts reads the source sentences exactly.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import type { KeyOrVar } from "@autobots/api-client";

import {
  FIELD,
  fieldLabel,
  ITEM_REMOVED,
  ITEM_SAVED,
  itemActionText,
  sourceLabel,
  TITLE,
  toggleValue,
} from "../../lib/keys-and-vars.ts";

function item(
  name: KeyOrVar["name"],
  kind: KeyOrVar["kind"],
  source: KeyOrVar["source"],
  value: string | null = null,
): KeyOrVar {
  return {
    kind,
    name,
    source,
    value,
    variable: name.toUpperCase(),
    version: 1,
  };
}

test("a source names where the value comes from, and a secret's is never its value", () => {
  assert.equal(
    sourceLabel(item("tavily", "secret", "settings")),
    "Saved here for this workspace, encrypted on this Mac",
  );
  assert.equal(
    sourceLabel(item("github_repository", "value", "settings", "o/n")),
    "Saved here for this workspace",
  );
  assert.equal(
    sourceLabel(item("jina", "secret", "environment")),
    "JINA from the server environment or .env",
  );
  assert.equal(
    sourceLabel(item("tavily", "secret", null)),
    "None. Its tools are unavailable",
  );
  assert.equal(
    sourceLabel(item("github_repository", "value", null)),
    "None. GITHUB_REPOSITORY isn't set",
  );
});

test("a field's label says whether it replaces a saved key or sets a value", () => {
  assert.equal(fieldLabel(item("tavily", "secret", null)), "API key");
  assert.equal(fieldLabel(item("tavily", "secret", "settings")), "Replace key");
  assert.equal(fieldLabel(item("tavily", "secret", "environment")), "API key");
  assert.equal(
    fieldLabel(item("browser_executor", "value", null)),
    "Set for this workspace",
  );
});

test("each item names its control, so no card checks an item's name", () => {
  assert.deepEqual(FIELD.browser_executor, { control: "toggle" });
  assert.deepEqual(FIELD.github_repository, {
    control: "text",
    placeholder: "owner/name",
  });
  assert.deepEqual(FIELD.tavily, { control: "text" });
  assert.equal(TITLE.browser_executor, "Browsing");
  assert.equal(
    toggleValue(item("browser_executor", "value", "settings", "enabled")),
    "enabled",
  );
  assert.equal(
    toggleValue(item("browser_executor", "value", null, null)),
    "disabled",
  );
});

test("a save or removal says what it did, this screen's words for a refusal, or that its reply was lost", () => {
  assert.equal(itemActionText(true, null, ITEM_SAVED), "Saved.");
  assert.equal(itemActionText(true, null, ITEM_REMOVED), "Removed.");
  assert.equal(
    itemActionText(false, { code: "owner_required", message: "x" }, ITEM_SAVED),
    "Only the workspace owner can save or remove one.",
  );
  assert.equal(
    itemActionText(
      false,
      { code: "invalid_value", message: "That isn't owner/name." },
      ITEM_SAVED,
    ),
    "That isn't owner/name.",
  );
  assert.equal(
    itemActionText(false, null, ITEM_SAVED),
    "The reply was lost, so this may have applied. What's shown is reloaded.",
  );
});
