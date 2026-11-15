/**
 * The charge an owner enters for a model call with no settled charge (R-49, WRUN-05): US dollars in,
 * exact micro-USD out, or the sentence that says why nothing is sent.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import { chargeEntry } from "../../lib/runs/charges.ts";

const ASK = "Enter the charge in US dollars, such as 0.0012.";
const TOO_SMALL =
  "That's under a millionth of a dollar, which can't be recorded. Enter 0 if there was no charge.";

test("a charge in dollars becomes whole micro-USD", () => {
  assert.deepEqual(chargeEntry("0.00025"), { micro: 250 });
  assert.deepEqual(chargeEntry(" 1.5 "), { micro: 1_500_000 });
  assert.deepEqual(chargeEntry("0"), { micro: 0 });
  assert.deepEqual(chargeEntry("0.0000014"), { micro: 1 });
});

test("an empty, negative or non-numeric entry asks for dollars", () => {
  for (const text of ["", "   ", "abc", "-1", "Infinity", "NaN"]) {
    assert.deepEqual(chargeEntry(text), { problem: ASK }, text);
  }
});

test("a charge under a millionth of a dollar can't be recorded", () => {
  assert.deepEqual(chargeEntry("0.0000004"), { problem: TOO_SMALL });
});
