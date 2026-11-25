/**
 * A browse's steps in the run's Tools used table (Decision 0035 Y11, US-17.4): only a browse_goal
 * use with steps offers them, each screenshot is read through the BFF, and a step reads as its host
 * and path.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import type { ToolUseView } from "@autobots/api-client";

import {
  browseStepCount,
  screenshotAlt,
  screenshotUrl,
  stepsLabel,
  stepTitle,
  touchText,
} from "../../lib/runs/browse-steps.ts";

function use(patch: Partial<ToolUseView>): ToolUseView {
  return {
    code: null,
    duration_ms: null,
    finished_at: null,
    group: null,
    id: 9,
    input_digest: "d",
    input_public: {},
    instance_key: null,
    operation_id: null,
    outcome: "succeeded",
    output_bytes: null,
    output_public: null,
    plan_version: null,
    provider: null,
    provider_units: null,
    requested_at: "2026-11-19T00:00:00Z",
    run_id: "run 1",
    sequence_in_run: 1,
    task_id: null,
    task_title: null,
    tool_id: "browse_goal",
    tool_version: 3,
    ...patch,
  };
}

test("only a browse_goal use with steps offers them", () => {
  assert.equal(browseStepCount(use({ output_public: { steps: 3 } })), 3);
  assert.equal(browseStepCount(use({ output_public: { steps: 0 } })), 0);
  assert.equal(browseStepCount(use({ output_public: null })), 0);
  assert.equal(browseStepCount(use({ output_public: { steps: "3" } })), 0);
  assert.equal(
    browseStepCount(
      use({ tool_id: "search_web", output_public: { steps: 3 } }),
    ),
    0,
  );
});

test("each screenshot is read through the BFF's authorized route", () => {
  assert.equal(
    screenshotUrl("run 1", 9, 2),
    "/api/v1/runs/run%201/tool-uses/9/steps/2/screenshot",
  );
});

test("a step reads as its host and path, and its screenshot says where it was", () => {
  const step = {
    step: 2,
    page: "a.test/search",
    submits: ["a.test/search"],
    touched: [],
    screenshot: true,
  };
  assert.equal(stepTitle(step), "Step 2: a.test/search");
  assert.equal(
    screenshotAlt(step),
    "Screenshot after step 2, on a.test/search",
  );
  assert.equal(stepTitle({ ...step, page: null }), "Step 2: no page");
  assert.equal(
    screenshotAlt({ ...step, page: null }),
    "Screenshot after step 2",
  );
  assert.equal(stepsLabel(1), "Show 1 step");
  assert.equal(stepsLabel(4), "Show 4 steps");
});

test("a stealth step says what it pressed or typed into, and never a value", () => {
  const touch = (action: "pressed" | "typed" | "chose", label: string) =>
    touchText({ action, kind: "button", label });
  assert.equal(touch("pressed", "Go"), 'Pressed "Go", button');
  assert.equal(touch("typed", "Search"), 'Typed into "Search", button');
  assert.equal(touch("chose", "Country"), 'Chose from "Country", button');
  assert.equal(touch("pressed", ""), "Pressed an unnamed button");
});
