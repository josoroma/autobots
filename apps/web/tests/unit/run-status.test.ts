/**
 * Pins the run vocabulary every screen shares, keyed by the generated RunStatus (R-37): the short
 * words, the run page's sentences, one tone per state and the terminal set. What a run offers comes
 * from the service (run-commands.test.ts).
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import type { RunStatus } from "@autobots/api-client";

import {
  isRunStatus,
  isTerminal,
  RUN_STATUS_LABEL,
  RUN_STATUS_SENTENCE,
  runStatusText,
  runTone,
  stopReasonText,
} from "../../lib/runs/status.ts";

const STATUSES: readonly RunStatus[] = [
  "queued",
  "running",
  "waiting_input",
  "waiting_approval",
  "paused",
  "verifying",
  "cancelling",
  "succeeded",
  "failed",
  "cancelled",
];

test("every status has the short words the list and the run page's header show", () => {
  assert.deepEqual(RUN_STATUS_LABEL, {
    queued: "Queued",
    running: "Running",
    waiting_input: "Waiting for input",
    waiting_approval: "Waiting for approval",
    paused: "Paused",
    verifying: "Verifying",
    cancelling: "Cancelling",
    succeeded: "Succeeded",
    failed: "Failed",
    cancelled: "Cancelled",
  });
  assert.deepEqual(Object.keys(RUN_STATUS_LABEL), STATUSES);
});

test("every status has the run page's sentence", () => {
  assert.deepEqual(RUN_STATUS_SENTENCE, {
    queued: "Queued. Waiting for a worker.",
    running: "Running.",
    waiting_input: "Waiting for your input.",
    waiting_approval: "Waiting for an approval decision.",
    paused: "Paused. No new work starts until it resumes.",
    verifying: "Checking the result against its criteria.",
    cancelling: "Cancelling. Active work is being settled.",
    succeeded: "Succeeded.",
    failed: "Failed.",
    cancelled: "Cancelled.",
  });
});

test("what runs is live, what waits for a person needs attention, and the rest stay neutral", () => {
  // Decision 0021 R3: requested input takes the attention tone and verifying is live on every
  // screen, and paused is neutral like the other states that wait for nothing (R-37).
  assert.deepEqual(Object.fromEntries(STATUSES.map((s) => [s, runTone(s)])), {
    queued: "idle",
    running: "live",
    waiting_input: "attention",
    waiting_approval: "attention",
    paused: "idle",
    verifying: "live",
    cancelling: "idle",
    succeeded: "success",
    failed: "failure",
    cancelled: "idle",
  });
});

test("only succeeded, failed and cancelled are terminal, as the service's TERMINAL says", () => {
  assert.deepEqual(STATUSES.filter(isTerminal), [
    "succeeded",
    "failed",
    "cancelled",
  ]);
  assert.equal(isTerminal("not_a_status"), false);
});

test("a status the contract types as a string is labelled when known, and shown as sent otherwise", () => {
  assert.equal(isRunStatus("waiting_approval"), true);
  assert.equal(isRunStatus("toString"), false);
  assert.equal(isRunStatus("archived"), false);
  assert.equal(runStatusText("waiting_approval"), "Waiting for approval");
  assert.equal(runStatusText("archived"), "archived");
});

test("a stop reason reads as its words", () => {
  // Every screen says a code whole, as the run page does (R-37).
  assert.equal(stopReasonText("budget_exhausted"), "budget exhausted");
  assert.equal(stopReasonText("tool_budget_exceeded"), "tool budget exceeded");
  assert.equal(stopReasonText("route_not_bound"), "route not bound");
});
