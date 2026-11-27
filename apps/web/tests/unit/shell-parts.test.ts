/**
 * Pins the shell's pure parts (PRD-Studio SH-01, SH-04, SH-05 and HM-05, Decision 0023 E3, WSHL-18,
 * WSHL-19): the account's initials, role labels and when the workspace chooser shows, the current
 * sidebar link, and each service state's words and tone.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import type { MemberReadiness } from "@autobots/api-client";

import { choosingWorkspace, initials, ROLE_LABEL } from "../../lib/account.ts";
import { currentHref } from "../../lib/nav.ts";
import {
  healthLine,
  READINESS,
  SERVICE_LABEL,
  stateWords,
} from "../../lib/readiness.ts";

test("initials take the first letter of two names, or two letters of one", () => {
  assert.equal(initials("Ada Lovelace"), "AL");
  assert.equal(initials("  grace   brewster hopper "), "GB");
  assert.equal(initials("ada"), "AD");
  assert.equal(initials("A"), "A");
  assert.equal(ROLE_LABEL.owner, "Owner");
  assert.equal(ROLE_LABEL.member, "Member");
});

test("the chooser shows for several workspaces or a stale choice, never for one unchosen", () => {
  const one = [{ id: "w-1" }];
  const two = [{ id: "w-1" }, { id: "w-2" }];
  assert.equal(choosingWorkspace(one, null, one[0] ?? null), false);
  assert.equal(choosingWorkspace(one, "w-1", one[0] ?? null), false);
  // A choice of a workspace this person no longer belongs to is stale.
  assert.equal(choosingWorkspace(one, "w-9", one[0] ?? null), true);
  assert.equal(choosingWorkspace(two, "w-2", two[1] ?? null), true);
  assert.equal(choosingWorkspace(two, null, null), true);
});

test("the longest matching link is current, and Home only on its own path", () => {
  const hrefs = ["/", "/runs", "/settings/models", "/settings"];
  assert.equal(currentHref("/", hrefs), "/");
  assert.equal(currentHref("/runs/abc", hrefs), "/runs");
  assert.equal(currentHref("/settings/models", hrefs), "/settings/models");
  assert.equal(currentHref("/settings/keyboard", hrefs), "/settings");
  assert.equal(currentHref("/runsheet", hrefs), undefined);
  assert.equal(currentHref("/elsewhere", hrefs), undefined);
});

test("each service state has its words, OpenRouter's own, and one tone for both views", () => {
  assert.equal(SERVICE_LABEL.api, "Python API");
  assert.equal(
    stateWords({ name: "worker", state: "not_ready", code: "x" }),
    "not ready",
  );
  assert.equal(
    stateWords({ name: "openrouter", state: "ready", code: "x" }),
    "authenticated",
  );
  assert.equal(
    stateWords({ name: "openrouter", state: "not_ready", code: "x" }),
    "not authenticated",
  );
  assert.equal(
    stateWords({ name: "database", state: "unknown", code: "x" }),
    "unknown",
  );
  // Decision 0041 A13: on Local, Home's model service reads from the runtime's health check.
  assert.equal(SERVICE_LABEL.local_model, "Local model");
  assert.equal(
    stateWords({ name: "local_model", state: "ready", code: "local_ready" }),
    "ready",
  );
  assert.equal(
    stateWords({
      name: "local_model",
      state: "not_ready",
      code: "local_not_running",
    }),
    "isn't running",
  );
  assert.deepEqual(
    Object.fromEntries(
      Object.entries(READINESS).map(([state, entry]) => [state, entry.tone]),
    ),
    { ready: "success", not_ready: "attention", unknown: "muted" },
  );
});

test("the health line names the first service that isn't ready, in its own tone", () => {
  const readiness = (
    states: MemberReadiness["services"][number]["state"][],
  ): MemberReadiness => ({
    ready: states.every((state) => state === "ready"),
    schema_version: 1,
    services: (["api", "worker", "database", "openrouter"] as const).map(
      (name, index) => ({ name, state: states[index] ?? "ready", code: "x" }),
    ),
  });
  assert.deepEqual(
    healthLine(readiness(["ready", "ready", "ready", "ready"])),
    {
      field: "ready",
      words: "All local services ready",
      tone: "success",
    },
  );
  assert.deepEqual(
    healthLine(readiness(["ready", "not_ready", "unknown", "ready"])),
    { field: "worker", words: "Worker not ready", tone: "attention" },
  );
  assert.deepEqual(
    healthLine(readiness(["ready", "ready", "unknown", "ready"])),
    { field: "database", words: "Database unknown", tone: "muted" },
  );
});
