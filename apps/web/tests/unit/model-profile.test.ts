import assert from "node:assert/strict";
import { test } from "node:test";

import {
  PROFILE_NAME,
  profileChoice,
  profileField,
  profileName,
} from "../../lib/model-profile.ts";

test("a select's choice is none, a profile, or ignored, so it never becomes a default", () => {
  assert.equal(profileChoice(""), "");
  assert.equal(profileChoice("openrouter_sol"), "openrouter_sol");
  assert.equal(profileChoice("terra"), null);
});

test("an empty choice means the default, so no field is sent", () => {
  assert.deepEqual(profileField(""), {});
});

test("a profile is sent as the contract's ModelProfileId", () => {
  assert.deepEqual(profileField("openrouter_sol"), {
    run_profile: "openrouter_sol",
  });
});

test("a value that isn't a profile is refused, never sent as the default", () => {
  assert.equal(profileField("gpt-5"), null);
  assert.equal(profileField("openai/gpt-unknown"), null);
});

test("each approved profile has one short name, for every screen that names it", () => {
  // The run list and the Experts page share this table. The composer's preview shows the label
  // the run preview sends, as /api/models carries no name (R-37).
  assert.deepEqual(PROFILE_NAME, {
    openrouter_terra: "Terra",
    openrouter_sol: "Sol",
    openrouter_deepseek_flash: "DeepSeek Flash",
  });
  assert.equal(profileName("openrouter_deepseek_flash"), "DeepSeek Flash");
});

test("a profile the contract types as a string is shown as sent when it isn't approved", () => {
  assert.equal(profileName("openai/gpt-unknown"), "openai/gpt-unknown");
  assert.equal(profileName("toString"), "toString");
});
