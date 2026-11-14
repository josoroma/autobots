/**
 * Pins the tool catalog's words, which the Tools page and the Expert editor share (R-37, WTAP-07):
 * the label tables keyed by the contract's unions, where a key comes from (PRD-Tool-Catalog PK-05)
 * and each repair sentence (TS-03).
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import type { ToolDescriptor } from "@autobots/api-client";

import {
  APPROVAL_TEXT,
  AVAILABILITY_FILTERS,
  AVAILABILITY_LABEL,
  COST_LABEL,
  keyOrigin,
  keySource,
  OPERATION_CLASS_LABEL,
  PROVIDER_LABEL,
  repairText,
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
