/**
 * What the disclosure before a run says it would use (MP-07, R-49, WRUN-05, WRUN-15): each role's
 * binding after an Expert's own and a run-wide choice, the server's rule that any binding not
 * offered refuses the whole run, and when the model and roles are shown.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  parseModelList,
  parseModelPolicyState,
  type ModelList,
  type ModelPolicyState,
} from "@autobots/api-client";

import { canonicalOf, resolveDisclosure } from "../../lib/runs/disclosure.ts";

const model = (profile: string, offered: boolean) => ({
  profile,
  canonical_id: `vendor/${profile}`,
  wire_id: `vendor/${profile}:wire`,
  available: true,
  offered,
  capabilities: [],
  input_per_million_micro_usd: null,
  output_per_million_micro_usd: null,
});

const MODELS: ModelList = parseModelList({
  schema_version: 1,
  catalog_status: "available",
  fetched_at: null,
  models: [
    model("openrouter_terra", true),
    model("openrouter_sol", true),
    model("openrouter_deepseek_flash", false),
  ],
});

function policy(executor: string, summarizer: string): ModelPolicyState {
  const binding = (role: string, profile: string) => ({
    role,
    profile,
    canonical_id: `vendor/${profile}`,
    wire_id: `vendor/${profile}`,
    source: "workspace_default",
  });
  return parseModelPolicyState({
    schema_version: 1,
    version: 1,
    default_profile: null,
    role_overrides: {},
    policy: {
      schema_version: 1,
      role_policy_version: 1,
      bindings: [
        binding("executor", executor),
        binding("summarizer", summarizer),
      ],
    },
  });
}

const BASE = {
  models: MODELS,
  policy: policy("openrouter_terra", "openrouter_terra"),
  chosen: "",
  roleOverrides: undefined,
  usesModel: true,
  failed: false,
};

test("with the workspace setting, each role keeps the policy's binding", () => {
  const shown = resolveDisclosure(BASE);
  assert.deepEqual(shown.bindings, [
    { role: "executor", profile: "openrouter_terra" },
    { role: "summarizer", profile: "openrouter_terra" },
  ]);
  assert.deepEqual(shown.executor, {
    role: "executor",
    profile: "openrouter_terra",
  });
  assert.equal(shown.refused, false);
  assert.equal(shown.showModel, true);
});

test("a run-wide choice replaces every role, and an Expert's own binding outranks it", () => {
  const chosen = resolveDisclosure({ ...BASE, chosen: "openrouter_sol" });
  assert.deepEqual(
    chosen.bindings.map((binding) => binding.profile),
    ["openrouter_sol", "openrouter_sol"],
  );
  const expert = resolveDisclosure({
    ...BASE,
    chosen: "openrouter_sol",
    roleOverrides: { summarizer: "openrouter_terra", executor: 7 },
  });
  assert.deepEqual(expert.bindings, [
    { role: "executor", profile: "openrouter_sol" },
    { role: "summarizer", profile: "openrouter_terra" },
  ]);
});

test("any binding not offered refuses the whole run, and says when it's the Expert's", () => {
  const workspace = resolveDisclosure({
    ...BASE,
    policy: policy("openrouter_terra", "openrouter_deepseek_flash"),
  });
  assert.equal(workspace.refused, true);
  assert.equal(workspace.fromExpert, false);
  assert.equal(workspace.showModel, false);
  const expert = resolveDisclosure({
    ...BASE,
    roleOverrides: { executor: "openrouter_deepseek_flash" },
  });
  assert.equal(expert.refused, true);
  assert.equal(expert.fromExpert, true);
});

test("a version that calls no model is never refused", () => {
  const shown = resolveDisclosure({
    ...BASE,
    policy: policy("openrouter_deepseek_flash", "openrouter_terra"),
    usesModel: false,
  });
  assert.equal(shown.refused, false);
  assert.equal(shown.showModel, true);
});

test("nothing about the model shows until the policy is read, or when the reads failed", () => {
  const unread = resolveDisclosure({ ...BASE, policy: null });
  assert.deepEqual(unread.bindings, []);
  assert.equal(unread.executor, null);
  assert.equal(unread.showModel, false);
  assert.equal(resolveDisclosure({ ...BASE, failed: true }).showModel, false);
  // Before the models are read, nothing counts as not offered.
  assert.equal(
    resolveDisclosure({
      ...BASE,
      models: null,
      policy: policy("openrouter_deepseek_flash", "openrouter_terra"),
    }).refused,
    false,
  );
});

test("a profile reads as its canonical model, or as itself when it isn't listed", () => {
  assert.equal(canonicalOf(MODELS, "openrouter_sol"), "vendor/openrouter_sol");
  assert.equal(canonicalOf(MODELS, "unlisted"), "unlisted");
  assert.equal(canonicalOf(null, "openrouter_sol"), "openrouter_sol");
});
