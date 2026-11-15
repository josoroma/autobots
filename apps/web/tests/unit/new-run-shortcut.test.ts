/**
 * PRD-Studio SH-02 and Decision 0022 D16: ⇧⌘O, or Shift+Ctrl+O, opens Home's composer, and Settings →
 * Keyboard lists the same definition the button and its matcher read (XWEB-18).
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import { NEW_RUN_SHORTCUT, SHORTCUTS } from "../../lib/shortcuts.ts";

const PRESS = {
  key: "O",
  code: "KeyO",
  shiftKey: true,
  metaKey: false,
  ctrlKey: false,
  altKey: false,
};

test("⇧⌘O or Shift+Ctrl+O opens the composer", () => {
  assert.equal(NEW_RUN_SHORTCUT.matches({ ...PRESS, metaKey: true }), true);
  assert.equal(NEW_RUN_SHORTCUT.matches({ ...PRESS, ctrlKey: true }), true);
});

test("without Shift, with Alt, or on another key, nothing opens", () => {
  const chord = { ...PRESS, metaKey: true };
  assert.equal(NEW_RUN_SHORTCUT.matches({ ...chord, shiftKey: false }), false);
  assert.equal(NEW_RUN_SHORTCUT.matches({ ...chord, altKey: true }), false);
  assert.equal(
    NEW_RUN_SHORTCUT.matches({ ...chord, code: "KeyP", key: "P" }),
    false,
  );
  assert.equal(NEW_RUN_SHORTCUT.matches(PRESS), false);
});

test("Settings → Keyboard lists the one definition, with its hint and aria name", () => {
  const anywhere = SHORTCUTS.find((group) => group.where === "Anywhere");
  assert.ok(anywhere?.shortcuts.includes(NEW_RUN_SHORTCUT));
  assert.equal(NEW_RUN_SHORTCUT.keys.join(""), "⇧⌘O");
  assert.equal(NEW_RUN_SHORTCUT.aria, "Shift+Meta+O Shift+Control+O");
});
