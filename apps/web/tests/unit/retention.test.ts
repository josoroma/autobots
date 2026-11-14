import assert from "node:assert/strict";
import { test } from "node:test";

import { parseDays } from "../../lib/retention.ts";

test("an empty window keeps everything", () => {
  assert.deepEqual(parseDays(""), { valid: true, days: null });
  assert.deepEqual(parseDays("   "), { valid: true, days: null });
});

test("whole days are read as typed", () => {
  assert.deepEqual(parseDays("30"), { valid: true, days: 30 });
  assert.deepEqual(parseDays(" 7 "), { valid: true, days: 7 });
  assert.deepEqual(parseDays("1000"), { valid: true, days: 1000 });
  // The contract refuses 0; this only reads it faithfully.
  assert.deepEqual(parseDays("0"), { valid: true, days: 0 });
});

for (const typed of [
  "1,000",
  "3O",
  "2e3",
  "7.9",
  "abc",
  "-5",
  "+5",
  "30 days",
  "１２",
  "99999999999999999999",
]) {
  test(`"${typed}" is refused rather than misread`, () => {
    assert.deepEqual(parseDays(typed), { valid: false });
  });
}
