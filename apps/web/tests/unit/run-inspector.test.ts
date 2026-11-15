/**
 * How the run inspector states one model call (R-49, WRUN-05): its outcome, its tokens, and which
 * charge it has, written once rather than three times in one row.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import type { ModelCallView } from "@autobots/api-client";

import { formatUsd } from "../../lib/format.ts";
import { callCharge, callOutcome, tokens } from "../../lib/runs/inspector.ts";

function call(patch: Partial<ModelCallView> = {}): ModelCallView {
  return {
    attempt: 1,
    canonical_id: "vendor/model",
    charge_source_unknown: false,
    created_at: "2026-11-15T00:00:00Z",
    estimated_micro_usd: 900,
    failure_class: null,
    finish_reason: "stop",
    id: "66666666-6666-4666-8666-666666666666",
    input_tokens: 10,
    outcome_unknown: false,
    output_tokens: 5,
    profile: "terra",
    provider: "openrouter",
    reasoning_tokens: null,
    reconciled: false,
    reported_micro_usd: null,
    role: "executor",
    run_id: "11111111-1111-4111-8111-111111111111",
    status: "failed_before_acceptance",
    upstream_provider: "Vendor",
    wire_id: "vendor/model",
    ...patch,
  };
}

test("a token count is a number, or says it wasn't reported", () => {
  assert.equal(tokens(0), "0");
  assert.equal(tokens(42), "42");
  assert.equal(tokens(null), "not reported");
});

test("an unknown outcome and an unattributed reconciliation say so before the status", () => {
  assert.equal(callOutcome(call()), "failed before acceptance");
  assert.equal(callOutcome(call({ outcome_unknown: true })), "outcome unknown");
  assert.equal(
    callOutcome(call({ charge_source_unknown: true })),
    "reconciled",
  );
  assert.equal(
    callOutcome(call({ outcome_unknown: true, charge_source_unknown: true })),
    "outcome unknown",
  );
});

test("a charge is the owner's entry, an unattributed one, or the provider's report", () => {
  assert.deepEqual(callCharge(call({ reported_micro_usd: 1200 })), {
    kind: "reported",
    label: "Reported charge:",
    amount: formatUsd(1200),
  });
  assert.deepEqual(
    callCharge(call({ reconciled: true, reported_micro_usd: 7 })),
    {
      kind: "entered",
      label: "Charge entered by the owner, from the provider's records:",
      amount: formatUsd(7),
    },
  );
  assert.deepEqual(callCharge(call({ charge_source_unknown: true })), {
    kind: "unattributed",
    label: "Charge reconciled, source not recorded:",
    amount: "none",
  });
  // An owner's entry outranks an unattributed source.
  assert.equal(
    callCharge(call({ reconciled: true, charge_source_unknown: true })).kind,
    "entered",
  );
});
