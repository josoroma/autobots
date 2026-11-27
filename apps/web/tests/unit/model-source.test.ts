/**
 * Pins the Model source panel's words (Decision 0041 A1, A7, A13; US-23.3): each local profile's
 * state, the runtime's health with its model ID and pinned SHA-256, the roles Local covers, and
 * what a call costs.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import type {
  LocalProfileState,
  LocalRuntime,
  ModelSourceState,
} from "@autobots/api-client";

import {
  matchedLine,
  NO_MATCH,
  profileLine,
  rolesLine,
  runtimeLine,
  SOURCE_CHOICES,
  SPEND_NOTE,
  TOOLS_NOTE,
} from "../../lib/model-source.ts";

const BONSAI: LocalProfileState = {
  profile: "local_bonsai_2_5_27b",
  name: "Bonsai 2.5",
  offered: true,
  reason: null,
  qualified_on: "2026-11-27",
  limits:
    "Not passed in every trial, so disabled: schema_nested passed 0 of 3.",
  matched_runs: [],
};
const INKLING: LocalProfileState = {
  profile: "local_inkling_2_mini",
  name: "Inkling 2 Mini",
  offered: false,
  reason:
    "Inkling 2 Mini isn't offered: its local route hasn't passed US-3.4's suite, and no qualification is stored.",
  qualified_on: null,
  limits: null,
  matched_runs: [],
};
const READY: LocalRuntime = {
  status: "ready",
  port: 9931,
  served_model_id: "bonsai-2.5-27b-q2_0",
  sha256_matches: true,
  sha256_checking: false,
};

function state(overrides: Partial<ModelSourceState>): ModelSourceState {
  return {
    schema_version: 1,
    version: 3,
    source: "openrouter",
    local_profile: null,
    local_profiles: [BONSAI, INKLING],
    roles_needed: ["executor", "researcher"],
    roles_uncovered: [],
    runtime: READY,
    ...overrides,
  };
}

test("OpenRouter comes first and Local says nothing goes to OpenRouter", () => {
  assert.deepEqual(
    SOURCE_CHOICES.map((choice) => choice.value),
    ["openrouter", "local"],
  );
  assert.match(SOURCE_CHOICES[1]?.detail ?? "", /Nothing goes to OpenRouter/);
});

test("each local profile reads as qualified with its date, or with why it isn't offered", () => {
  assert.equal(
    profileLine(BONSAI),
    "Qualified 2026-11-27 · llama-server · 64K context",
  );
  assert.match(profileLine(INKLING), /^Inkling 2 Mini isn't offered/);
  assert.equal(matchedLine(BONSAI), NO_MATCH);
  assert.equal(
    matchedLine({ ...BONSAI, matched_runs: ["Market watcher"] }),
    "Matched: Market watcher",
  );
});

test("the runtime names the model it serves and whether its file matches the pin", () => {
  assert.equal(
    runtimeLine(READY),
    'Ready: serving "bonsai-2.5-27b-q2_0" on 127.0.0.1:9931, pinned SHA-256 matches.',
  );
  assert.match(
    runtimeLine({ ...READY, sha256_matches: false }),
    /doesn't match the pinned SHA-256/,
  );
  assert.match(
    runtimeLine({ ...READY, sha256_matches: null, sha256_checking: true }),
    /checking its file's SHA-256/,
  );
  assert.equal(
    runtimeLine({ ...READY, status: "not_running", served_model_id: null }),
    "Not running on 127.0.0.1:9931. Start it with the runbook command.",
  );
  assert.match(
    runtimeLine({ ...READY, status: "other_model", served_model_id: "x" }),
    /Serving "x" on 127.0.0.1:9931, not this profile's model/,
  );
  assert.equal(runtimeLine(null), "No local profile is offered yet.");
});

test("the roles say what Local covers, or which ones keep it from being chosen", () => {
  assert.equal(
    rolesLine(state({})),
    "executor and researcher use the local model, as every role does on Local.",
  );
  assert.equal(
    rolesLine(state({ roles_uncovered: ["executor"] })),
    "No offered local profile covers executor yet, so Local can't be chosen.",
  );
});

test("a call costs nothing, and tool calls still leave the Mac", () => {
  assert.match(SPEND_NOTE, /^US\$0\.00 per model call/);
  assert.match(TOOLS_NOTE, /SerpApi, Jina and YouTube still leave the Mac/);
});
