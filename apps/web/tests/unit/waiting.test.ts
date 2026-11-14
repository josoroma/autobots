import assert from "node:assert/strict";
import { test } from "node:test";

import {
  EVERY_MS,
  MAX_MS,
  newlyWaiting,
  pollDelay,
  SIGNED_OUT_MS,
} from "../../lib/waiting.ts";

const run = (id: string, status: string) => ({ id, status });

test("the first poll only notes what already waits", () => {
  const { fresh, seen } = newlyWaiting(null, [
    run("a", "waiting_approval"),
    run("b", "running"),
  ]);
  assert.deepEqual(fresh, []);
  assert.deepEqual([...seen], ["a:waiting_approval"]);
});

test("a later poll tells each run that newly waits, once", () => {
  const first = newlyWaiting(null, [run("a", "waiting_approval")]);
  const second = newlyWaiting(first.seen, [
    run("a", "waiting_approval"),
    run("b", "waiting_input"),
    run("c", "succeeded"),
  ]);
  assert.deepEqual(second.fresh, [run("b", "waiting_input")]);
  const third = newlyWaiting(second.seen, [
    run("a", "waiting_input"),
    run("b", "waiting_input"),
  ]);
  assert.deepEqual(third.fresh, [run("a", "waiting_input")]);
  assert.deepEqual([...third.seen].sort(), [
    "a:waiting_input",
    "b:waiting_input",
  ]);
});

test("polling continues after every outcome, slower when signed out and backing off after failures", () => {
  assert.equal(pollDelay("runs", 0), EVERY_MS);
  assert.equal(pollDelay("signed_out", 0), SIGNED_OUT_MS);
  assert.deepEqual(
    [1, 2, 3, 4, 5, 12].map((failures) => pollDelay("failed", failures)),
    [8_000, 16_000, 32_000, MAX_MS, MAX_MS, MAX_MS],
  );
  assert.equal(EVERY_MS, 4_000);
  assert.equal(MAX_MS, 60_000);
});
