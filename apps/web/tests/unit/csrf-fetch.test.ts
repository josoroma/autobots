import assert from "node:assert/strict";
import { test } from "node:test";

import { csrfFetch, forgetCsrfToken } from "../../lib/csrf-fetch.ts";

function stub(replies: (url: string, call: number) => Response) {
  const calls: { url: string; token: string | undefined }[] = [];
  globalThis.fetch = (async (
    input: string | URL | Request,
    init?: RequestInit,
  ) => {
    const url = String(input);
    const headers = (init?.headers ?? {}) as Record<string, string>;
    calls.push({ url, token: headers["x-autobots-csrf"] });
    return replies(url, calls.length);
  }) as typeof fetch;
  return calls;
}

const token = (value: string) =>
  new Response(JSON.stringify({ header: "x-autobots-csrf", token: value }));

test("overlapping writes share one token fetch", async () => {
  forgetCsrfToken();
  const calls = stub((url) =>
    url === "/api/csrf" ? token("t1") : new Response("{}", { status: 200 }),
  );
  await Promise.all([
    csrfFetch("/api/v1/a", { method: "POST" }),
    csrfFetch("/api/v1/b", { method: "POST" }),
  ]);
  assert.equal(calls.filter((call) => call.url === "/api/csrf").length, 1);
  assert.deepEqual(
    calls.filter((call) => call.url !== "/api/csrf").map((call) => call.token),
    ["t1", "t1"],
  );
});

test("a write refused for its token fetches a fresh one and is sent once more", async () => {
  forgetCsrfToken();
  let minted = 0;
  const calls = stub((url, call) => {
    if (url === "/api/csrf") return token(`t${++minted}`);
    return call === 2
      ? new Response(JSON.stringify({ code: "invalid_csrf", message: "x" }), {
          status: 403,
        })
      : new Response("{}", { status: 200 });
  });
  const reply = await csrfFetch("/api/v1/a", { method: "POST", body: "{}" });
  assert.equal(reply.status, 200);
  assert.deepEqual(
    calls.map((call) => call.url),
    ["/api/csrf", "/api/v1/a", "/api/csrf", "/api/v1/a"],
  );
  assert.deepEqual(
    calls.filter((call) => call.url === "/api/v1/a").map((call) => call.token),
    ["t1", "t2"],
  );
});

test("any other refusal is returned as it is, and not resent", async () => {
  forgetCsrfToken();
  const calls = stub((url) =>
    url === "/api/csrf"
      ? token("t1")
      : new Response(
          JSON.stringify({ code: "forbidden_origin", message: "x" }),
          { status: 403 },
        ),
  );
  assert.equal((await csrfFetch("/api/v1/a", { method: "POST" })).status, 403);
  assert.equal(calls.filter((call) => call.url === "/api/v1/a").length, 1);
});
