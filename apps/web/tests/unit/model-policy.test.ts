/**
 * Pins Settings → Models' policy rules (PRD-Studio MD-01 to MD-03, WSYS-06): what counts as a
 * change, which profiles each select offers, whether a saved choice is no longer offered, how many
 * roles follow the workspace default, and the bodies and words of a save and a reset.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import type {
  ModelAvailability,
  ModelPolicyState,
  RoleBinding,
} from "@autobots/api-client";

import {
  BUILTIN_DEFAULT,
  choices,
  draftOf,
  fetchedAt,
  followingCount,
  modelLabel,
  perMillion,
  policyBody,
  resetBody,
  sameForm,
  savedChoiceNotOffered,
  sourceText,
  withOverride,
} from "../../lib/model-policy.ts";

function model(
  profile: ModelAvailability["profile"],
  offered: boolean,
): ModelAvailability {
  return {
    available: true,
    canonical_id: `vendor/${profile}`,
    capabilities: [],
    input_per_million_micro_usd: 1_250_000,
    offered,
    output_per_million_micro_usd: null,
    profile,
    wire_id: profile,
  };
}

function binding(
  role: RoleBinding["role"],
  source: RoleBinding["source"],
): RoleBinding {
  return {
    canonical_id: "vendor/terra",
    profile: "openrouter_terra",
    role,
    source,
    wire_id: "terra",
  };
}

function policy(
  default_profile: ModelPolicyState["default_profile"],
  role_overrides: ModelPolicyState["role_overrides"],
  bindings: RoleBinding[] = [],
): ModelPolicyState {
  return {
    default_profile,
    policy: { bindings, role_policy_version: 1, schema_version: 1 },
    role_overrides,
    schema_version: 1,
    version: 7,
  };
}

const MODELS = [
  model("openrouter_terra", true),
  model("openrouter_sol", true),
  model("openrouter_deepseek_flash", false),
];

test("the form starts as saved, and only a different default or override is a change", () => {
  const saved = policy(null, { coder: "openrouter_terra" });
  const draft = draftOf(saved);
  assert.deepEqual(draft, {
    defaultProfile: BUILTIN_DEFAULT,
    overrides: { coder: "openrouter_terra" },
  });
  assert.equal(sameForm(saved, draft), true);
  assert.equal(
    sameForm(saved, { ...draft, defaultProfile: "openrouter_sol" }),
    false,
  );
  assert.equal(sameForm(saved, { ...draft, overrides: {} }), false);
  assert.equal(
    sameForm(saved, {
      ...draft,
      overrides: { coder: "openrouter_terra", planner: "openrouter_sol" },
    }),
    false,
  );
  assert.equal(
    sameForm(policy("openrouter_sol", {}), {
      defaultProfile: "openrouter_sol",
      overrides: {},
    }),
    true,
  );
});

test("choosing Workspace default removes a role's override, and the old overrides are kept", () => {
  const before = { coder: "openrouter_terra" };
  assert.deepEqual(withOverride(before, "planner", "openrouter_sol"), {
    coder: "openrouter_terra",
    planner: "openrouter_sol",
  });
  assert.deepEqual(withOverride(before, "coder", ""), {});
  assert.deepEqual(before, { coder: "openrouter_terra" });
});

test("a select offers the offered profiles, and a saved choice that isn't offered stays visible", () => {
  assert.deepEqual(
    choices(MODELS, undefined).map((item) => item.profile),
    ["openrouter_terra", "openrouter_sol"],
  );
  assert.deepEqual(
    choices(MODELS, "openrouter_deepseek_flash").map((item) => item.profile),
    ["openrouter_terra", "openrouter_sol", "openrouter_deepseek_flash"],
  );
});

test("a saved default or override naming a profile that isn't offered is reported", () => {
  assert.equal(savedChoiceNotOffered(policy(null, {}), MODELS), false);
  assert.equal(
    savedChoiceNotOffered(policy("openrouter_deepseek_flash", {}), MODELS),
    true,
  );
  assert.equal(
    savedChoiceNotOffered(
      policy("openrouter_terra", { coder: "openrouter_deepseek_flash" }),
      MODELS,
    ),
    true,
  );
});

test("roles bound by either default follow the workspace default", () => {
  assert.equal(
    followingCount([
      binding("coder", "workspace_override"),
      binding("planner", "workspace_default"),
      binding("researcher", "builtin_default"),
      binding("executor", "run_override"),
    ]),
    2,
  );
  assert.equal(sourceText("builtin_default"), "Built-in default");
  assert.equal(sourceText(undefined), "Not recorded");
});

test("prices, the fetch time and a model's label read as the suites expect", () => {
  assert.equal(perMillion(1_250_000), "US$1.25");
  assert.equal(perMillion(null), "not listed");
  assert.equal(fetchedAt(null), "The catalog couldn't be fetched.");
  assert.match(
    fetchedAt("2026-11-15T10:20:30Z"),
    /^Catalog fetched Nov 15, 2026, \d{1,2}:\d{2}:\d{2}\s?[AP]M\.$/,
  );
  assert.equal(
    modelLabel("openai/gpt-6.1-terra", "terra-wire"),
    "openai/gpt-6.1-terra (requested as terra-wire)",
  );
});

test("a save sends the version it was loaded at, and the built-in default as null", () => {
  const saved = policy("openrouter_terra", {});
  assert.deepEqual(
    JSON.parse(
      policyBody(saved, {
        defaultProfile: BUILTIN_DEFAULT,
        overrides: { coder: "openrouter_sol" },
      }),
    ),
    {
      expected_version: 7,
      default_profile: null,
      role_overrides: { coder: "openrouter_sol" },
    },
  );
  assert.deepEqual(
    JSON.parse(
      policyBody(saved, { defaultProfile: "openrouter_sol", overrides: {} }),
    ).default_profile,
    "openrouter_sol",
  );
  assert.deepEqual(JSON.parse(resetBody(saved)), { expected_version: 7 });
});
