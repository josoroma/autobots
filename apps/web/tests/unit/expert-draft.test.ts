/**
 * Pins how the Expert editor turns a saved version into a draft and a draft into a revision
 * (WBLD-10, R-59): the defaults, which other role bindings a save keeps or drops (Decision 0013,
 * Decision 0019 S2), a body that keeps what the form doesn't edit, each reply's words from one
 * table, the executor's choices and a version's summary.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import type { ExpertView, ModelList } from "@autobots/api-client";

import {
  domainsOf,
  draftOf,
  executorOptions,
  grantsBrowsing,
  offeredFor,
  revisionBody,
  revisionText,
  SAVE_LOST,
  SAVE_REFUSALS,
  splitBindings,
  versionToolsText,
  WORKSPACE_SETTING,
  type Draft,
  type RevisionReply,
} from "../../lib/experts/draft.ts";
import { HELD_NOTE } from "../../lib/submit.ts";

const expert = (
  config: ExpertView["versions"][number]["config"] = {},
  latest = 2,
): ExpertView => ({
  id: "e-1",
  name: "Writer",
  latest_version: latest,
  last_run_at: null,
  run_count: 0,
  schema_version: 1,
  versions: [
    { version: 1, config: {} },
    { version: latest, config },
  ],
});

const model = (
  profile: ModelList["models"][number]["profile"],
  offered: boolean,
): ModelList["models"][number] => ({
  profile,
  offered,
  available: true,
  canonical_id: profile,
  capabilities: [],
  input_per_million_micro_usd: null,
  output_per_million_micro_usd: null,
  wire_id: profile,
});

const models = (...entries: ModelList["models"]): ModelList => ({
  catalog_status: "available",
  fetched_at: null,
  models: entries,
  schema_version: 1,
});

const draft = (changes: Partial<Draft> = {}): Draft => ({
  purpose: "Writes",
  instructions: "Be brief.",
  tools: ["calculate"],
  groups: [],
  executor: WORKSPACE_SETTING,
  browseDomains: "",
  ...changes,
});

test("a draft comes from the latest version, with empty defaults", () => {
  assert.deepEqual(draftOf(expert()), {
    purpose: "",
    instructions: "",
    tools: [],
    groups: [],
    executor: "",
    browseDomains: "",
  });
  assert.deepEqual(
    draftOf(
      expert({
        purpose: "Writes",
        instructions: "Be brief.",
        tools: ["read_csv"],
        tool_groups: ["files"],
        role_bindings: {
          executor: "openrouter_terra",
          coder: "openrouter_sol",
        },
        browse_domains: ["youtube.com", "ytimg.com"],
      }),
    ),
    {
      purpose: "Writes",
      instructions: "Be brief.",
      tools: ["read_csv"],
      groups: ["files"],
      executor: "openrouter_terra",
      browseDomains: "youtube.com\nytimg.com",
    },
  );
});

test("a profile is offered as the models say, and unknown before they're read", () => {
  const list = models(
    model("openrouter_terra", true),
    model("openrouter_sol", false),
  );
  assert.equal(offeredFor(list, "openrouter_terra"), true);
  assert.equal(offeredFor(list, "openrouter_sol"), false);
  assert.equal(offeredFor(list, "openrouter_deepseek_flash"), false);
  assert.equal(offeredFor(null, "openrouter_terra"), null);
});

test("a save keeps the other offered bindings and drops one that isn't offered", () => {
  const saved = expert({
    role_bindings: {
      executor: "openrouter_terra",
      coder: "openrouter_sol",
      reviewer: "openrouter_terra",
    },
  });
  const list = models(
    model("openrouter_terra", true),
    model("openrouter_sol", false),
  );
  assert.deepEqual(splitBindings(saved, list), {
    kept: { reviewer: "openrouter_terra" },
    dropped: ["coder"],
  });
  // Until the models are read, every binding stays, and the service refuses one it doesn't offer.
  assert.deepEqual(splitBindings(saved, null), {
    kept: { coder: "openrouter_sol", reviewer: "openrouter_terra" },
    dropped: [],
  });
  assert.deepEqual(splitBindings(expert(), list), { kept: {}, dropped: [] });
});

test("a revision keeps what the form doesn't edit, and binds the executor only when chosen", () => {
  const saved = expert({ skills: ["summarize"], purpose: "Old", tools: [] }, 3);
  assert.deepEqual(
    revisionBody(saved, draft(), { reviewer: "openrouter_terra" }),
    {
      expected_version: 3,
      config: {
        skills: ["summarize"],
        purpose: "Writes",
        instructions: "Be brief.",
        tools: ["calculate"],
        tool_groups: [],
        browse_domains: [],
        role_bindings: { reviewer: "openrouter_terra" },
      },
    },
  );
  const chosen = revisionBody(
    saved,
    draft({ executor: "openrouter_sol", groups: ["files"] }),
    {},
  );
  assert.deepEqual(chosen.config.role_bindings, { executor: "openrouter_sol" });
  assert.deepEqual(chosen.config.tool_groups, ["files"]);
  const browsing = revisionBody(
    saved,
    draft({ browseDomains: "en.wikivoyage.org" }),
    {},
  );
  assert.deepEqual(browsing.config.browse_domains, ["en.wikivoyage.org"]);
});

test("each reply has its words, from one table of refusals", () => {
  const reply = (changes: Partial<RevisionReply>): RevisionReply => ({
    outcome: "refused",
    value: null,
    refusal: null,
    held: false,
    ...changes,
  });
  assert.equal(
    revisionText(reply({ outcome: "accepted", value: expert({}, 4) })),
    "Saved as version 4. Work already started keeps its version.",
  );
  assert.equal(revisionText(reply({ outcome: "unknown" })), SAVE_LOST);
  assert.equal(
    revisionText(
      reply({
        refusal: { code: "model_not_offered", message: "The service's words." },
      }),
    ),
    "The service's words.",
  );
  for (const [code, words] of Object.entries(SAVE_REFUSALS)) {
    assert.equal(
      revisionText(reply({ refusal: { code, message: "not shown" } })),
      words,
    );
  }
  assert.equal(
    revisionText(
      reply({ refusal: { code: "something_else", message: "not shown" } }),
    ),
    "That could not be saved.",
  );
  assert.equal(
    revisionText(
      reply({ refusal: { code: "owner_required", message: "" }, held: true }),
    ),
    `Only the workspace owner can save a revision. ${HELD_NOTE}`,
  );
  assert.equal(
    revisionText(reply({ outcome: "accepted" })),
    "That could not be saved.",
  );
});

test("the executor offers the workspace setting and each offered profile, and keeps a saved one shown", () => {
  const list = models(
    model("openrouter_terra", true),
    model("openrouter_sol", false),
  );
  assert.deepEqual(executorOptions(WORKSPACE_SETTING, list), {
    offered: [{ profile: "openrouter_terra", label: "Terra" }],
    saved: null,
  });
  assert.deepEqual(executorOptions("openrouter_terra", list).saved, null);
  assert.deepEqual(executorOptions("openrouter_sol", list).saved, {
    label: "openrouter_sol: not offered for new runs until qualified",
    disabled: true,
  });
  // Until the models are read, the saved choice shows as it is.
  assert.deepEqual(executorOptions("openrouter_sol", null), {
    offered: [],
    saved: { label: "Sol", disabled: false },
  });
  assert.deepEqual(executorOptions("retired_profile", null).saved, {
    label: "retired_profile",
    disabled: false,
  });
});

test("a version's summary names its tools and groups", () => {
  assert.equal(versionToolsText({}), "no tools");
  assert.equal(versionToolsText({ tools: [] }), "no tools");
  assert.equal(
    versionToolsText({ tools: ["calculate", "read_csv"] }),
    "calculate, read_csv",
  );
  assert.equal(
    versionToolsText({
      tools: ["read_csv"],
      tool_groups: ["files", "general"],
    }),
    "read_csv (groups: files, general)",
  );
  assert.equal(
    versionToolsText({ tool_groups: ["files"] }),
    "no tools (groups: files)",
  );
});

test("browse domains are typed one per line or by commas, and saved once each", () => {
  assert.deepEqual(
    domainsOf(" en.wikivoyage.org\nYouTube.com, ytimg.com,\n\nyoutube.com "),
    ["en.wikivoyage.org", "youtube.com", "ytimg.com"],
  );
  assert.deepEqual(domainsOf(""), []);
});

test("the browse domains matter only while the draft grants browse_goal", () => {
  assert.equal(grantsBrowsing(draft()), false);
  assert.equal(grantsBrowsing(draft({ tools: ["browse_goal"] })), true);
  assert.equal(grantsBrowsing(draft({ groups: ["browsing"] })), true);
});
