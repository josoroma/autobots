import assert from "node:assert/strict";
import { test } from "node:test";

import {
  apiHeaders,
  bodyLimit,
  cookieOptions,
  forwardedHeaders,
  MAX_BODY_BYTES,
  readJsonObject,
  relayHeaders,
  routeTemplate,
  RUN_BODY_BYTES,
  WORKSPACE_HEADER,
} from "../../lib/bff-policy.ts";

const WORKSPACE = "a0000000-0000-4000-8000-000000000001";
const OTHER = "b0000000-0000-4000-8000-000000000002";

test("only run creation gets the attachment allowance", () => {
  assert.equal(bodyLimit("POST", "/v1/runs"), RUN_BODY_BYTES);
  assert.equal(bodyLimit("POST", "/v1/runs?draft=1"), RUN_BODY_BYTES);
  assert.equal(bodyLimit("GET", "/v1/runs"), MAX_BODY_BYTES);
  assert.equal(bodyLimit("POST", "/v1/runs/intent"), MAX_BODY_BYTES);
  assert.equal(bodyLimit("PUT", "/v1/settings/model-policy"), MAX_BODY_BYTES);
});

test("the API headers carry the internal token, the bearer and the chosen workspace", () => {
  assert.deepEqual(apiHeaders("internal", "token", WORKSPACE), {
    "X-Autobots-Internal": "internal",
    Authorization: "Bearer token",
    [WORKSPACE_HEADER]: WORKSPACE,
  });
  assert.deepEqual(apiHeaders("internal", null, null), {
    "X-Autobots-Internal": "internal",
  });
});

test("only allowlisted request headers are forwarded, and a browser's workspace replaces the chosen one", () => {
  const request = new Headers({
    "content-type": "application/json",
    [WORKSPACE_HEADER]: OTHER,
    "idempotency-key": "key-1",
    "x-autobots-internal": "client-value",
    authorization: "Bearer forged",
    cookie: "autobots.session=x",
    host: "evil.example",
  });
  const sent = forwardedHeaders(
    request,
    apiHeaders("internal", "token", WORKSPACE),
  );
  assert.deepEqual(Object.fromEntries(sent.entries()), {
    authorization: "Bearer token",
    "content-type": "application/json",
    "idempotency-key": "key-1",
    "x-autobots-internal": "internal",
    [WORKSPACE_HEADER]: OTHER,
  });
});

test("a relayed reply is never cached and keeps only its allowlisted headers", () => {
  const relayed = relayHeaders(
    new Headers({
      "content-type": "text/csv",
      "content-disposition": 'attachment; filename="a.csv"',
      "x-content-type-options": "nosniff",
      "set-cookie": "autobots.session=leak",
      "x-autobots-internal": "leak",
      server: "uvicorn",
    }),
  );
  assert.deepEqual(Object.fromEntries(relayed.entries()), {
    "cache-control": "no-store",
    "content-disposition": 'attachment; filename="a.csv"',
    "content-type": "text/csv",
    "x-content-type-options": "nosniff",
  });
  assert.equal(
    relayHeaders(new Headers()).get("content-type"),
    "application/json",
  );
});

test("cookies are strict, site-wide, and Secure only on an https origin", () => {
  assert.deepEqual(cookieOptions("http://127.0.0.1:3000", true), {
    httpOnly: true,
    sameSite: "strict",
    path: "/",
    secure: false,
  });
  assert.equal(cookieOptions("https://autobots.example", false).secure, true);
  assert.equal(
    cookieOptions("https://autobots.example", false).httpOnly,
    false,
  );
});

test("a JSON body is read only as an object", async () => {
  const body = (text: string) =>
    new Request("http://127.0.0.1:3000/api/x", { method: "POST", body: text });
  assert.deepEqual(await readJsonObject(body('{"workspace_id":"w"}')), {
    workspace_id: "w",
  });
  for (const text of ["[1]", "null", '"w"', "{", ""]) {
    assert.equal(await readJsonObject(body(text)), null, text);
  }
});

test("a logged route is a template, with no query, identifier or value", () => {
  assert.equal(
    routeTemplate(`/v1/runs/${OTHER}/events/stream?after=12`),
    "/v1/runs/{param}/events/stream",
  );
  assert.equal(
    routeTemplate(`/v1/workspaces/${WORKSPACE}`),
    "/v1/workspaces/{param}",
  );
  assert.equal(routeTemplate("/v1/runs?group=needs_you&q=private"), "/v1/runs");
  assert.equal(
    routeTemplate("/v1/settings/keys-and-vars/GITHUB_TOKEN"),
    "/v1/settings/keys-and-vars/{param}",
  );
  assert.equal(
    routeTemplate("/v1/tools/calculate/versions/1"),
    "/v1/tools/calculate/versions/{param}",
  );
  assert.equal(routeTemplate("/v1/a%2Fb#frag"), "/v1/{param}");
});
