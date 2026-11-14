import assert from "node:assert/strict";
import { test } from "node:test";

import { ContractError, HttpFailure } from "@autobots/api-client/runtime";
import {
  AuthApiError,
  AuthRetryableFetchError,
  AuthUnknownError,
} from "@supabase/supabase-js";

import {
  API_TIMEOUT,
  API_UNAVAILABLE,
  AUTH_UNAVAILABLE,
  failureRecord,
  failureRefusal,
  MISCONFIGURED,
  readFailure,
  SIGN_IN_FAILED,
  signInRefusal,
  timedOut,
} from "../../lib/failure.ts";
import { ConfigurationError } from "../../lib/server-env.ts";

const timeout = () =>
  new DOMException("The operation was aborted due to timeout", "TimeoutError");
const refused = () =>
  new TypeError("fetch failed", {
    cause: new Error("connect ECONNREFUSED 127.0.0.1:8001"),
  });
const AT = new Date("2026-11-14T12:00:00.000Z");

test("a timeout fired when the error or its cause is a TimeoutError", () => {
  assert.equal(timedOut(timeout()), true);
  assert.equal(
    timedOut(new TypeError("fetch failed", { cause: timeout() })),
    true,
  );
  assert.equal(timedOut(refused()), false);
  assert.equal(timedOut(new DOMException("aborted", "AbortError")), false);
  assert.equal(timedOut("TimeoutError"), false);
});

test("the BFF tells its own timeout, an Auth outage and missing configuration from an unreachable API", () => {
  assert.deepEqual(failureRefusal(timeout()), API_TIMEOUT);
  assert.equal(API_TIMEOUT.status, 504);
  assert.equal(API_TIMEOUT.code, "upstream_timeout");
  assert.deepEqual(failureRefusal(refused()), API_UNAVAILABLE);
  assert.equal(API_UNAVAILABLE.code, "service_unavailable");
  assert.deepEqual(
    failureRefusal(new AuthRetryableFetchError("fetch failed", 0)),
    AUTH_UNAVAILABLE,
  );
  assert.deepEqual(
    failureRefusal(new ConfigurationError(["AUTOBOTS_INTERNAL_TOKEN"])),
    MISCONFIGURED,
  );
  assert.equal(MISCONFIGURED.status, 503);
  assert.equal(MISCONFIGURED.code, "server_misconfigured");
});

test("a route that depends on Auth reports an unknown failure as Auth unavailable", () => {
  assert.deepEqual(failureRefusal(refused(), "auth"), AUTH_UNAVAILABLE);
  assert.deepEqual(
    failureRefusal(
      new ConfigurationError(["AUTOBOTS_SUPABASE_ANON_KEY"]),
      "auth",
    ),
    MISCONFIGURED,
  );
});

test("only Auth's own refusal of the credentials is a wrong password", () => {
  assert.deepEqual(
    signInRefusal(
      new AuthApiError("Invalid login credentials", 400, "invalid_credentials"),
    ),
    SIGN_IN_FAILED,
  );
  assert.equal(SIGN_IN_FAILED.status, 401);
  for (const error of [
    new AuthRetryableFetchError("fetch failed", 0),
    new AuthRetryableFetchError("Bad Gateway", 502),
    new AuthApiError("Internal error", 500, "unexpected_failure"),
    new AuthApiError("Too many requests", 429, "over_request_rate_limit"),
    new AuthUnknownError("not JSON", null),
    new Error("unexpected"),
  ]) {
    assert.deepEqual(signInRefusal(error), AUTH_UNAVAILABLE, error.message);
  }
  assert.equal(AUTH_UNAVAILABLE.status, 503);
  assert.equal(AUTH_UNAVAILABLE.code, "auth_unavailable");
});

test("a member read is signed out only on a 401, and unavailable otherwise", () => {
  assert.equal(
    readFailure(new HttpFailure("/v1/session", 401, null)),
    "signed_out",
  );
  for (const error of [
    new HttpFailure("/v1/session", 403, null),
    new HttpFailure("/v1/session", 404, null),
    new HttpFailure("/v1/session", 503, null),
    new ContractError(
      "SessionSummary.workspaces[0].role",
      "not an allowed value",
    ),
    timeout(),
    refused(),
    new ConfigurationError(["AUTOBOTS_INTERNAL_TOKEN"]),
    new AuthRetryableFetchError("fetch failed", 0),
  ]) {
    assert.equal(readFailure(error), "unavailable", error.message);
  }
});

test("the log record names the operation, class, contract path, status and timeout", () => {
  assert.deepEqual(
    failureRecord(
      "session.read",
      new ContractError(
        "SessionSummary.workspaces[0].role",
        "not an allowed value",
      ),
      AT,
    ),
    {
      at: "2026-11-14T12:00:00.000Z",
      level: "error",
      logger: "web",
      event: "web.failure",
      operation: "session.read",
      error: "ContractError",
      path: "SessionSummary.workspaces[0].role",
      timeout: false,
    },
  );
  const http = failureRecord(
    "readiness.read",
    new HttpFailure("/v1/readiness", 500, null),
    AT,
  );
  assert.equal(http.status, 500);
  assert.equal(http.error, "HttpFailure");
  assert.equal("path" in http, false);
  const slow = failureRecord("GET /v1/runs", timeout(), AT);
  assert.equal(slow.error, "TimeoutError");
  assert.equal(slow.timeout, true);
  assert.equal("status" in slow, false);
  assert.equal(
    failureRecord("auth.sign_in", new AuthRetryableFetchError("x", 0), AT)
      .status,
    0,
  );
});

test("the log record never carries a message, query, token or value", () => {
  const records = [
    failureRecord(
      "session.read",
      new HttpFailure("/v1/runs?token=query-secret", 401, {
        code: "unauthorized",
        message: "envelope-secret",
      }),
      AT,
    ),
    failureRecord("GET /v1/runs", new Error("Bearer header-secret"), AT),
    failureRecord(
      "session.read",
      new ConfigurationError(["AUTOBOTS_INTERNAL_TOKEN"]),
      AT,
    ),
    failureRecord("session.read", "thrown-secret", AT),
    failureRecord(
      "session.read",
      Object.assign(new Error("x"), { name: "Bearer name-secret" }),
      AT,
    ),
  ];
  const text = JSON.stringify(records);
  for (const secret of [
    "query-secret",
    "envelope-secret",
    "header-secret",
    "AUTOBOTS_INTERNAL_TOKEN",
    "thrown-secret",
    "name-secret",
  ]) {
    assert.equal(text.includes(secret), false, secret);
  }
  assert.equal(records[2]?.error, "ConfigurationError");
  assert.equal(records[3]?.error, "string");
  assert.equal(records[4]?.error, "Error");
  for (const record of records) {
    assert.deepEqual(
      Object.keys(record).filter(
        (key) =>
          ![
            "at",
            "level",
            "logger",
            "event",
            "operation",
            "error",
            "path",
            "status",
            "timeout",
          ].includes(key),
      ),
      [],
    );
  }
});
