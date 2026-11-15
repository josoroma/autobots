/**
 * Pins Settings → Models' provider words (PRD-Model-Providers, WSYS-07): the connection bar's
 * source, authentication and catalog, each route's qualification, and what a key action says.
 * settings.spec.ts and qualification.spec.ts read several of these sentences exactly.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  AUTH_LABEL,
  AUTH_TONE,
  CATALOG_LABEL,
  CATALOG_TONE,
  keyActionText,
  KEY_DISCONNECTED,
  KEY_VALIDATED,
  QUALIFICATION_LABEL,
  QUALIFICATION_TONE,
  SOURCE_LABEL,
} from "../../lib/provider-text.ts";

test("the connection bar names the source, the key's status and the catalog's", () => {
  assert.equal(SOURCE_LABEL.none, "None");
  assert.match(SOURCE_LABEL.app, /encrypted/);
  assert.match(SOURCE_LABEL.environment, /server environment/);
  assert.equal(AUTH_LABEL.configured, "The key authenticated.");
  assert.match(AUTH_LABEL.missing, /^No key is configured/);
  assert.equal(CATALOG_LABEL.available, "Available");
  assert.match(CATALOG_LABEL.unavailable, /^Unavailable/);
  assert.equal(CATALOG_LABEL.unknown, "Not checked");
});

test("each status dot repeats its words: good, bad or not yet known", () => {
  assert.deepEqual(AUTH_TONE, {
    missing: "idle",
    configured: "ok",
    invalid: "bad",
    unavailable: "bad",
  });
  assert.deepEqual(CATALOG_TONE, {
    available: "ok",
    unavailable: "bad",
    unknown: "idle",
  });
});

test("a route reads as qualified with limits, or not qualified", () => {
  assert.equal(
    QUALIFICATION_LABEL.qualified_with_limits,
    "Qualified, with the limits below",
  );
  assert.equal(QUALIFICATION_LABEL.not_qualified, "Not qualified");
  assert.equal(QUALIFICATION_TONE.qualified_with_limits, "success");
  assert.equal(QUALIFICATION_TONE.not_qualified, "muted");
});

test("a key action says what it did, this screen's words for a refusal, or that its reply was lost", () => {
  assert.equal(keyActionText(true, null, KEY_VALIDATED), KEY_VALIDATED);
  assert.equal(KEY_VALIDATED, "Checked. The key's status above is current.");
  assert.equal(KEY_DISCONNECTED, "Disconnected. The saved key is removed.");
  assert.equal(
    keyActionText(false, { code: "owner_required", message: "x" }, "Saved."),
    "Only the workspace owner can change the OpenRouter key.",
  );
  assert.equal(
    keyActionText(
      false,
      { code: "credential_rejected", message: "The key was not accepted." },
      "Saved.",
    ),
    "The key was not accepted.",
  );
  assert.equal(
    keyActionText(false, null, "Saved."),
    "The reply was lost, so this may have applied. The status above is reloaded.",
  );
});
