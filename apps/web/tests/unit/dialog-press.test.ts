/**
 * Decision 0026 G2: a click outside a dialog closes it, and a press that began inside does not, even
 * when it is released over the backdrop.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import { closesDialog, spotOf } from "../../lib/dialog-press.ts";

const BOX = { left: 100, right: 500, top: 100, bottom: 400 };
const BACKDROP = spotOf(BOX, { x: 4, y: 4 }, true);
const PADDING = spotOf(BOX, { x: 300, y: 110 }, true);
const FIELD = spotOf(BOX, { x: 300, y: 200 }, false);

test("a press and release on the backdrop close the dialog", () => {
  assert.equal(closesDialog(BACKDROP, BACKDROP), true);
});

test("a press inside released over the backdrop keeps it open", () => {
  assert.equal(closesDialog(FIELD, BACKDROP), false);
  assert.equal(closesDialog(PADDING, BACKDROP), false);
});

test("a press on the backdrop released inside keeps it open", () => {
  assert.equal(closesDialog(BACKDROP, PADDING), false);
});

test("a click on the dialog's own padding keeps it open", () => {
  assert.equal(closesDialog(PADDING, PADDING), false);
});

test("a click with no press seen, such as one a key made, keeps it open", () => {
  assert.equal(closesDialog(null, BACKDROP), false);
});

test("a point on the box's edge is inside", () => {
  assert.equal(spotOf(BOX, { x: 100, y: 400 }, true).outside, false);
  assert.equal(spotOf(BOX, { x: 99.5, y: 200 }, true).outside, true);
});
