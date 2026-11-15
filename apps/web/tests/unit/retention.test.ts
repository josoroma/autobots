import assert from "node:assert/strict";
import { test } from "node:test";

import {
  parseDays,
  RETENTION_SAVED,
  retentionOutcome,
  retentionRequest,
} from "../../lib/retention.ts";

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

// R-59: the retention form's request and outcome, which the Operations suites read.
test("two windows in the contract's range make one request", () => {
  assert.deepEqual(retentionRequest("30", "60"), {
    body: JSON.stringify({ run_days: 30, receipt_days: 60 }),
    invalid: { run: false, receipt: false },
  });
  assert.deepEqual(retentionRequest("", " "), {
    body: JSON.stringify({ run_days: null, receipt_days: null }),
    invalid: { run: false, receipt: false },
  });
});

test("a malformed or out-of-range window is marked, and nothing is sent", () => {
  assert.deepEqual(retentionRequest("1,000", "7"), {
    body: null,
    invalid: { run: true, receipt: false },
  });
  assert.deepEqual(retentionRequest("0", "36501"), {
    body: null,
    invalid: { run: true, receipt: true },
  });
  assert.deepEqual(retentionRequest("36500", "1"), {
    body: JSON.stringify({ run_days: 36500, receipt_days: 1 }),
    invalid: { run: false, receipt: false },
  });
});

test("a save says what happened: saved, refused with the pairing rule, or lost", () => {
  assert.equal(retentionOutcome(true, null), RETENTION_SAVED);
  assert.equal(
    retentionOutcome(false, { code: "invalid_request", message: "x" }),
    "Not saved. Retry keys need a run content window at least as short.",
  );
  assert.equal(
    retentionOutcome(false, {
      code: "owner_required",
      message: "Owners only.",
    }),
    "Not saved. Owners only.",
  );
  assert.equal(
    retentionOutcome(false, null),
    "The reply was lost, so this may have saved. Saving again sends these windows again.",
  );
});

test("both windows are marked when both are refused, one malformed and one out of range", () => {
  assert.deepEqual(retentionRequest("1,000", "0"), {
    body: null,
    invalid: { run: true, receipt: true },
  });
});
