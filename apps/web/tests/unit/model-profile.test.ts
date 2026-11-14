import assert from "node:assert/strict";
import { test } from "node:test";

import { profileField } from "../../lib/model-profile.ts";

test("an empty choice means the default, so no field is sent", () => {
  assert.deepEqual(profileField(""), {});
});

test("a profile is sent as the contract's ModelProfileId", () => {
  assert.deepEqual(profileField("openrouter_sol"), {
    run_profile: "openrouter_sol",
  });
});

test("a value that isn't a profile is never sent", () => {
  assert.deepEqual(profileField("gpt-5"), {});
});
