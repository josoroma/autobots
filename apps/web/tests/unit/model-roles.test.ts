/**
 * Pins the role-binding rules that the run page, the disclosure before a run and Settings → Models
 * share (R-37, WRUN-11): which roles differ from the executor, whether the summarizer does, and the
 * words for where a binding came from (PRD-Studio MD-02).
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  BINDING_SOURCE_LABEL,
  differingRoles,
  summarizerDiffers,
} from "../../lib/model-roles.ts";

const TERRA = "openrouter_terra";
const SOL = "openrouter_sol";

test("a summarizer bound to the executor's profile doesn't differ", () => {
  assert.equal(
    summarizerDiffers([
      { role: "executor", profile: TERRA },
      { role: "summarizer", profile: TERRA },
      { role: "coder", profile: SOL },
    ]),
    false,
  );
});

test("a summarizer bound to another profile differs", () => {
  assert.equal(
    summarizerDiffers([
      { role: "executor", profile: TERRA },
      { role: "summarizer", profile: SOL },
    ]),
    true,
  );
});

test("no summarizer binding differs, as the service then has no compaction route", () => {
  // goal_loop's _summary_route compares the summarizer's binding to the executor's, and no binding
  // gives no route, so Settings says so too (R-37).
  assert.equal(summarizerDiffers([{ role: "executor", profile: TERRA }]), true);
});

test("the roles that differ are every role but the executor bound elsewhere", () => {
  assert.deepEqual(
    differingRoles([
      { role: "executor", profile: TERRA },
      { role: "summarizer", profile: TERRA },
      { role: "coder", profile: SOL },
      { role: "researcher", profile: SOL },
    ]),
    ["coder", "researcher"],
  );
  assert.deepEqual(
    differingRoles([
      { role: "executor", profile: TERRA },
      { role: "planner", profile: TERRA },
    ]),
    [],
  );
});

test("each binding source has its words", () => {
  assert.deepEqual(BINDING_SOURCE_LABEL, {
    run_override: "Run override",
    workspace_override: "Workspace override",
    workspace_default: "Workspace default",
    builtin_default: "Built-in default",
  });
});
