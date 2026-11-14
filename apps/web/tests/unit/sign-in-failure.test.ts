import assert from "node:assert/strict";
import { test } from "node:test";

import {
  SIGN_IN_FAILURE_TEXT,
  signInFailure,
} from "../../lib/sign-in-failure.ts";

test("only a 401 says the email and password did not work", () => {
  assert.equal(signInFailure(401), "credentials");
  assert.equal(
    SIGN_IN_FAILURE_TEXT.credentials,
    "That email and password did not work.",
  );
});

test("a refusal asks for a reload, and an outage or no reply says sign-in is unavailable", () => {
  assert.equal(signInFailure(403), "refused");
  for (const status of [null, 500, 502, 503, 504, 413]) {
    assert.equal(signInFailure(status), "unavailable", String(status));
  }
  assert.notEqual(
    SIGN_IN_FAILURE_TEXT.unavailable,
    SIGN_IN_FAILURE_TEXT.credentials,
  );
});
