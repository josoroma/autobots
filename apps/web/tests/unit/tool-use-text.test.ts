/**
 * How a tool use reads in a run's Tools used table and the workflow monitor (PRD-Tool-Catalog
 * TV-01 to TV-03, R-49, WRUN-15): its public inputs and result in brief, and its outcome in words.
 * Only public fields reach these texts.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import type { ToolUseView } from "@autobots/api-client";

import {
  brief,
  toolOutcome,
  toolResult,
  toolUseWhen,
} from "../../lib/runs/tool-uses.ts";

function use(patch: Partial<ToolUseView> = {}): ToolUseView {
  return {
    code: null,
    duration_ms: null,
    finished_at: null,
    group: null,
    id: 1,
    input_digest: "d",
    input_public: {},
    instance_key: null,
    operation_id: null,
    outcome: null,
    output_bytes: null,
    output_public: null,
    plan_version: null,
    provider: null,
    provider_units: null,
    requested_at: "2026-11-15T10:20:30Z",
    run_id: "11111111-1111-4111-8111-111111111111",
    sequence_in_run: 1,
    task_id: null,
    task_title: null,
    tool_id: "web_search",
    tool_version: 1,
    ...patch,
  };
}

test("public values read as key and value, each cut to 80 characters", () => {
  assert.equal(brief(null), "");
  assert.equal(brief({}), "");
  assert.equal(
    brief({ query: "weather", limit: 3, tags: ["a"] }),
    'query: weather; limit: 3; tags: ["a"]',
  );
  const long = "x".repeat(100);
  assert.equal(brief({ text: long }), `text: ${"x".repeat(79)}…`);
  assert.equal(brief({ text: "y".repeat(80) }), `text: ${"y".repeat(80)}`);
});

test("a result is its public output, else its size, else that nothing came back", () => {
  assert.equal(toolResult(use({ output_public: { hits: 2 } })), "hits: 2");
  assert.equal(
    toolResult(use({ output_public: {}, output_bytes: 512 })),
    "512 bytes, not shown",
  );
  assert.equal(toolResult(use()), "Nothing returned");
});

test("every outcome has its words, and a code follows it", () => {
  assert.equal(toolOutcome(use()), "Not finished");
  assert.equal(toolOutcome(use({ outcome: "succeeded" })), "Succeeded");
  assert.equal(toolOutcome(use({ outcome: "failed" })), "Failed");
  assert.equal(toolOutcome(use({ outcome: "unknown" })), "Outcome unknown");
  assert.equal(toolOutcome(use({ outcome: "denied" })), "Denied");
  assert.equal(
    toolOutcome(use({ outcome: "failed", code: "rate_limited" })),
    "Failed: rate limited",
  );
});

test("when is the request's local time, then how long it took once known", () => {
  const time = toolUseWhen(use());
  assert.doesNotMatch(time, /ms$/);
  assert.equal(toolUseWhen(use({ duration_ms: 42 })), `${time}, 42 ms`);
});
