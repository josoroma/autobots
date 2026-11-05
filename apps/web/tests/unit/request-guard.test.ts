import assert from "node:assert/strict";
import { test } from "node:test";

import { guardRequest, type GuardInput } from "../../lib/request-guard.ts";

const policy = { allowedOrigin: "http://127.0.0.1:3000" };
const write: GuardInput = {
  method: "POST",
  host: "127.0.0.1:3000",
  origin: "http://127.0.0.1:3000",
  fetchSite: "same-origin",
  csrfHeader: "token",
  csrfCookie: "token",
};
const read: GuardInput = {
  ...write,
  method: "GET",
  origin: null,
  csrfHeader: null,
  csrfCookie: null,
};

test("a same-origin write with a matching token passes", () => {
  assert.equal(guardRequest(write, policy), null);
});

test("a same-origin read passes without a token", () => {
  assert.equal(guardRequest(read, policy), null);
});

for (const [name, input, reason] of [
  [
    "forged host on a read",
    { ...read, host: "evil.example" },
    "forbidden_host",
  ],
  ["missing host", { ...read, host: null }, "forbidden_host"],
  [
    "DNS rebinding through a localhost alias",
    { ...read, host: "localhost:3000" },
    "forbidden_host",
  ],
  [
    "forged origin on a write",
    { ...write, origin: "http://evil.example" },
    "forbidden_origin",
  ],
  [
    "forged origin on a read",
    { ...read, origin: "http://evil.example" },
    "forbidden_origin",
  ],
  ["a write with no origin", { ...write, origin: null }, "forbidden_origin"],
  [
    "a cross-site fetch",
    { ...write, fetchSite: "cross-site" },
    "forbidden_origin",
  ],
  [
    "a same-site fetch from another port",
    { ...read, fetchSite: "same-site" },
    "forbidden_origin",
  ],
  ["a missing header", { ...write, csrfHeader: null }, "missing_csrf"],
  ["a missing cookie", { ...write, csrfCookie: null }, "missing_csrf"],
  [
    "an empty cookie and header",
    { ...write, csrfHeader: "", csrfCookie: "" },
    "missing_csrf",
  ],
  ["mismatched tokens", { ...write, csrfHeader: "other" }, "invalid_csrf"],
] as const) {
  test(`refuses ${name}`, () => {
    assert.equal(guardRequest(input, policy), reason);
  });
}
