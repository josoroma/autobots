/**
 * The BFF's own bodies (R-48): the routes read sign-in and workspace requests with these parsers,
 * and the browser parses the routes' replies and the CSRF token with them.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import { ContractError } from "@autobots/api-client/runtime";

import {
  parseCsrfToken,
  parseSessionState,
  parseWorkspaceChoice,
  readSignInRequest,
  readWorkspaceChoice,
} from "../../lib/api/bff-bodies.ts";

test("sign-in needs a non-empty email and password, and ignores anything else", () => {
  assert.deepEqual(
    readSignInRequest({ email: "a@example.test", password: "pw", extra: 1 }),
    { email: "a@example.test", password: "pw" },
  );
  for (const body of [
    { email: "", password: "pw" },
    { email: "a@example.test", password: "" },
    { email: "a@example.test" },
    { email: 1, password: "pw" },
    null,
    ["a@example.test", "pw"],
  ]) {
    assert.equal(readSignInRequest(body), null, JSON.stringify(body));
  }
});

test("a workspace choice names its workspace as a string", () => {
  assert.deepEqual(readWorkspaceChoice({ workspace_id: "w1" }), {
    workspace_id: "w1",
  });
  for (const body of [{ workspace_id: 1 }, {}, null, "w1"]) {
    assert.equal(readWorkspaceChoice(body), null);
  }
});

test("the BFF's replies parse, and a drifted one is a contract error", () => {
  assert.deepEqual(parseSessionState({ signed_in: true }), { signed_in: true });
  assert.deepEqual(parseWorkspaceChoice({ workspace_id: "w1" }), {
    workspace_id: "w1",
  });
  assert.deepEqual(parseCsrfToken({ header: "x-autobots-csrf", token: "t" }), {
    header: "x-autobots-csrf",
    token: "t",
  });
  assert.throws(() => parseSessionState({ signed_in: "yes" }), ContractError);
  assert.throws(() => parseWorkspaceChoice([]), ContractError);
  assert.throws(() => parseCsrfToken({ header: "x" }), ContractError);
  assert.throws(() => parseCsrfToken("token"), ContractError);
});
