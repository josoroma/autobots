/**
 * Pins the tool catalog's words, which the Tools page and the Expert editor share (R-37, WTAP-07):
 * the label tables keyed by the contract's unions, where a key comes from (PRD-Tool-Catalog PK-05),
 * each repair sentence (TS-03), and a row's facts and a detail's cost, limits and field constraints
 * (TS-01, WTAP-08).
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import type { ToolDescriptor } from "@autobots/api-client";

import {
  APPROVAL_TEXT,
  AVAILABILITY_FILTERS,
  AVAILABILITY_LABEL,
  constraintText,
  COST_LABEL,
  costText,
  grantorText,
  groupSwitchText,
  keyOrigin,
  keySource,
  limitsText,
  networkText,
  OPERATION_CLASS_LABEL,
  PROVIDER_LABEL,
  repairText,
  rowFacts,
  switchText,
  type ToolState,
} from "../../lib/tools/text.ts";

type Requirement = NonNullable<ToolDescriptor["key_requirement"]>;

const tool = (changes: Partial<ToolState> = {}): ToolState => ({
  availability: "available",
  availability_reason: null,
  key_requirement: null,
  ...changes,
});

const requirement = (changes: Partial<Requirement> = {}): Requirement => ({
  credential: "tavily",
  scopes: [],
  source: null,
  variables: ["TAVILY_API_KEY"],
  ...changes,
});

test("every contract value has its label", () => {
  assert.deepEqual(PROVIDER_LABEL, {
    autobots: "Autobots, on this Mac",
    tavily: "Tavily",
    jina: "Jina",
    serpapi: "SerpApi (Google)",
    direct: "Directly from each site",
    yahoo_finance: "Yahoo Finance",
    world_bank: "World Bank",
    github: "GitHub",
  });
  assert.deepEqual(OPERATION_CLASS_LABEL, {
    pure: "Pure",
    read_only: "Read only",
    reversible_internal_write: "Writes inside the run",
    consequential_external_write: "Changes something outside",
    arbitrary_execution: "Arbitrary execution",
  });
  assert.deepEqual(COST_LABEL, {
    free_local: "No provider charge",
    metered_provider: "Metered by its provider",
  });
  assert.deepEqual(AVAILABILITY_LABEL, {
    available: "Available",
    key_missing: "Unavailable: key not set",
    disabled_by_policy: "Unavailable: disabled by policy",
    not_qualified: "Unavailable: not qualified",
  });
  assert.deepEqual(AVAILABILITY_FILTERS, [
    "available",
    "key_missing",
    "disabled_by_policy",
  ]);
  assert.deepEqual(APPROVAL_TEXT, {
    always: "Every call waits for a person",
    unless_yolo: "Every call waits for a person, unless YOLO is on",
    by_action: "Some actions wait for a person",
    never: "Not needed",
  });
});

test("a key's source is named, never the key", () => {
  assert.equal(keySource(tool()), null);
  assert.equal(
    keySource(tool({ key_requirement: requirement({ source: "settings" }) })),
    "Key saved in Settings → Keys & vars for this workspace",
  );
  assert.equal(
    keySource(
      tool({
        key_requirement: requirement({
          source: "environment",
          variables: ["A_KEY", "B_KEY"],
        }),
      }),
    ),
    "A_KEY, B_KEY, from the server environment or .env",
  );
  assert.equal(
    keySource(tool({ key_requirement: requirement() })),
    "TAVILY_API_KEY, not set",
  );
});

test("an available tool's row says where its key comes from", () => {
  assert.equal(keyOrigin(tool()), null);
  assert.equal(
    keyOrigin(tool({ key_requirement: requirement({ source: "settings" }) })),
    "Key from Settings",
  );
  assert.equal(
    keyOrigin(
      tool({ key_requirement: requirement({ source: "environment" }) }),
    ),
    "Key from the environment",
  );
  assert.equal(keyOrigin(tool({ key_requirement: requirement() })), null);
  assert.equal(
    keyOrigin(
      tool({
        availability: "key_missing",
        key_requirement: requirement({ source: "settings" }),
      }),
    ),
    null,
  );
});

test("a missing key that Settings can hold says to save it there or in .env", () => {
  assert.equal(
    repairText(
      tool({ availability: "key_missing", key_requirement: requirement() }),
    ),
    "Save a Tavily key in Settings → Keys & vars, or set TAVILY_API_KEY in .env, then restart the worker and the API.",
  );
  assert.equal(
    repairText(
      tool({
        availability: "key_missing",
        key_requirement: requirement({
          credential: "jina",
          variables: ["JINA_API_KEY"],
        }),
      }),
    ),
    "Save a Jina key in Settings → Keys & vars, or set JINA_API_KEY in .env, then restart the worker and the API.",
  );
  // Decision 0032 G7: google_search's key is saved the same way.
  assert.equal(
    repairText(
      tool({
        availability: "key_missing",
        key_requirement: requirement({
          credential: "serpapi",
          variables: ["SERPAPI_API_KEY"],
        }),
      }),
    ),
    "Save a SerpApi key in Settings → Keys & vars, or set SERPAPI_API_KEY in .env, then restart the worker and the API.",
  );
});

test("another missing key names its variables and any permissions, never a value", () => {
  assert.equal(
    repairText(
      tool({
        availability: "key_missing",
        key_requirement: requirement({
          credential: "github",
          variables: ["GITHUB_TOKEN", "GITHUB_REPOSITORY"],
          scopes: ["issues: write", "metadata: read"],
        }),
      }),
    ),
    "Save them in Settings → Keys & vars, or set GITHUB_TOKEN and GITHUB_REPOSITORY in .env. The token needs these permissions on that repository only: issues: write, metadata: read. After a change to .env, restart the worker and the API.",
  );
  assert.equal(
    repairText(
      tool({
        availability: "key_missing",
        key_requirement: requirement({
          credential: "other",
          variables: ["OTHER_KEY"],
        }),
      }),
    ),
    "Save them in Settings → Keys & vars, or set OTHER_KEY in .env. After a change to .env, restart the worker and the API.",
  );
});

test("browsing waits for its executor, and an unqualified tool for its provider", () => {
  assert.equal(
    repairText(
      tool({
        availability: "disabled_by_policy",
        availability_reason: "isolated_executor_not_qualified",
      }),
    ),
    "Disabled until the isolated browser executor is qualified and browsing is turned on in Settings → Keys & vars or .env. See the operations runbook.",
  );
  assert.equal(
    repairText(tool({ availability: "not_qualified" })),
    "Waits for its provider's qualification.",
  );
});

test("an available tool, or one disabled for another reason, needs no repair", () => {
  assert.equal(repairText(tool()), null);
  assert.equal(repairText(tool({ availability: "disabled_by_policy" })), null);
  // A missing key with no requirement recorded has nothing to name.
  assert.equal(repairText(tool({ availability: "key_missing" })), null);
});

test("a catalog row's facts name provider, class, where it runs and cost, then the key's origin", () => {
  const row = {
    provider: "autobots",
    operation_class: "pure",
    network: false,
    cost_class: "free_local",
  } as const;
  assert.equal(
    rowFacts({ ...row, ...tool() }),
    "· Autobots, on this Mac · Pure · Stays on this Mac · No provider charge",
  );
  assert.equal(
    rowFacts({
      ...row,
      provider: "tavily",
      operation_class: "read_only",
      network: true,
      cost_class: "metered_provider",
      ...tool({ key_requirement: requirement({ source: "settings" }) }),
    }),
    "· Tavily · Read only · Leaves this Mac · Metered by its provider · Key from Settings",
  );
});

test("a tool's cost, network, limits and grantors are said in words", () => {
  assert.equal(networkText(true), "Leaves this Mac");
  assert.equal(networkText(false), "Stays on this Mac");
  assert.equal(
    costText({ cost_class: "free_local", cost_note: null }),
    "No provider charge",
  );
  assert.equal(
    costText({ cost_class: "metered_provider", cost_note: "per search" }),
    "Metered by its provider, per search",
  );
  assert.equal(limitsText(null), "Not registered");
  assert.equal(
    limitsText({ timeout_seconds: 30, retries: 2, max_output_bytes: 65536 }),
    "30 s, 2 retries, 65536 output bytes",
  );
  assert.equal(grantorText("workflow_node"), "workflow node");
  assert.equal(grantorText("expert"), "expert");
});

test("a field's constraints read as the schema states them, or None", () => {
  assert.equal(constraintText({}), "None");
  assert.equal(
    constraintText({ minimum: 0, enum: ["sum", "mean"] }),
    'minimum 0, enum ["sum","mean"]',
  );
});

test("a switch says its state in words, and a turned-off tool how to turn it on (Decision 0033 W2, W5)", () => {
  assert.equal(switchText({ switch: null }), null);
  assert.equal(
    switchText({ switch: { enabled: true, version: 0, by: null } }),
    "On for this workspace",
  );
  assert.equal(
    switchText({ switch: { enabled: false, version: 1, by: "tool" } }),
    "Off for this workspace",
  );
  assert.equal(
    switchText({ switch: { enabled: true, version: 2, by: "group" } }),
    "Off with its group",
  );
  assert.equal(groupSwitchText({ switch: null }), null);
  assert.equal(
    groupSwitchText({ switch: { enabled: false, version: 1, by: null } }),
    "Group off for this workspace",
  );
  assert.equal(
    repairText(
      tool({
        availability: "disabled_by_policy",
        availability_reason: "turned_off",
      }),
    ),
    "Turned off for this workspace. The workspace owner can turn it on here in Tools.",
  );
  assert.equal(
    repairText(
      tool({
        availability: "disabled_by_policy",
        availability_reason: "group_turned_off",
      }),
    ),
    "Its group is turned off for this workspace. The workspace owner can turn the group on here in Tools.",
  );
});
