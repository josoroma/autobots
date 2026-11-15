/**
 * How a failed read is classified, the same way in the browser and in a Server Component (R-27,
 * R-67, XERR-03, XTYP-14). A page read on the server can't be arranged with `page.route`, so the
 * out-of-date state, which no running service can be made to answer, is pinned here.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import { ContractError, HttpFailure } from "@autobots/api-client/runtime";

import { failureWords, OUT_OF_DATE } from "../../lib/load.ts";
import { loadFailure, worstFailure } from "../../lib/load-failure.ts";
import { ConfigurationError } from "../../lib/server-env.ts";

const refused = (status: number, message: string | null = null) =>
  new HttpFailure(
    "/v1/runs",
    status,
    message === null ? null : { code: "arranged", message },
  );

test("a 401 is signed out, and a 403 is denied with the service's message when it sent one", () => {
  assert.deepEqual(loadFailure(refused(401)), { kind: "signed_out" });
  assert.deepEqual(loadFailure(refused(403, "Choose a workspace.")), {
    kind: "denied",
    message: "Choose a workspace.",
  });
  assert.deepEqual(loadFailure(refused(403)), {
    kind: "denied",
    message: null,
  });
});

test("a 404 and a 422 are not found", () => {
  assert.deepEqual(loadFailure(refused(404)), { kind: "not_found" });
  assert.deepEqual(loadFailure(refused(422)), { kind: "not_found" });
});

test("a 5xx, a timeout, missing configuration and no reply are unavailable", () => {
  assert.deepEqual(loadFailure(refused(503)), {
    kind: "unavailable",
    status: 503,
  });
  const timeout = new DOMException("The read timed out.", "TimeoutError");
  for (const error of [
    new TypeError("fetch failed", { cause: timeout }),
    timeout,
    new ConfigurationError(["AUTOBOTS_API_URL"]),
    "not an error",
  ]) {
    assert.deepEqual(loadFailure(error), {
      kind: "unavailable",
      status: null,
    });
  }
});

test("a reply that drifted from its contract is out of date, naming the schema and field only", () => {
  const failure = loadFailure(
    new ContractError("RunInspector.model_calls", "expected an array"),
  );
  assert.deepEqual(failure, {
    kind: "out_of_date",
    schema: "RunInspector",
    path: "RunInspector.model_calls",
  });
  assert.deepEqual(failureWords(failure, "this run"), {
    words: OUT_OF_DATE,
    retry: false,
  });
  // A reply that isn't JSON names its route, which has no query.
  assert.deepEqual(
    loadFailure(new ContractError("/v1/retention", "not JSON")),
    { kind: "out_of_date", schema: null, path: "/v1/retention" },
  );
  const long = loadFailure(
    new ContractError(`ToolVersions.${"x".repeat(400)}`, "drifted"),
  );
  assert.equal(long.kind === "out_of_date" && long.path.length, 200);
});

test("of the reads one section shows, the failure the person must act on first is shown", () => {
  const down = { kind: "unavailable", status: 503 } as const;
  const drifted = {
    kind: "out_of_date",
    schema: "RunList",
    path: "x",
  } as const;
  assert.equal(worstFailure([{ kind: "ready" }, { kind: "ready" }]), null);
  assert.deepEqual(worstFailure([down, drifted]), drifted);
  assert.deepEqual(worstFailure([down, { kind: "signed_out" }, drifted]), {
    kind: "signed_out",
  });
});
