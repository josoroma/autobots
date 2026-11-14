import assert from "node:assert/strict";
import { test } from "node:test";

import { parseSearchResults } from "@autobots/api-client";

import {
  backoff,
  failureWords,
  loadJson,
  mismatchRecord,
  OUT_OF_DATE,
  readsInFlight,
  worstFailure,
  type Loaded,
  type LoadFailure,
} from "../../lib/load.ts";

// One read's classification, shared by every screen that reads through lib/load.ts (XERR-03,
// XERR-04, refactor plan R-27).

const FOUND = { schema_version: 1, query: "a", results: [] };

interface Arranged {
  readonly fetch: typeof globalThis.fetch;
  readonly calls: { url: string; init: RequestInit | undefined }[];
  readonly replies: Response[];
}

/** A fetch that answers each call with `answer()`, and records what it was asked and replied. */
function arrange(answer: () => Response | Promise<Response>): Arranged {
  const calls: Arranged["calls"] = [];
  const replies: Response[] = [];
  return {
    calls,
    replies,
    fetch: async (input, init) => {
      calls.push({ url: String(input), init });
      const reply = await answer();
      replies.push(reply);
      return reply;
    },
  };
}

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });

async function load(
  path: string,
  answer: () => Response | Promise<Response>,
): Promise<{ loaded: Loaded<unknown>; arranged: Arranged }> {
  const arranged = arrange(answer);
  const loaded = await loadJson(path, parseSearchResults, {
    fetch: arranged.fetch,
  });
  return { loaded, arranged };
}

test("a ready read is parsed, asked for with GET and never from the HTTP cache", async () => {
  const { loaded, arranged } = await load("/api/v1/search?q=a", () =>
    json(200, FOUND),
  );
  assert.deepEqual(loaded, { kind: "ready", value: FOUND });
  assert.equal(arranged.calls.length, 1);
  assert.equal(arranged.calls[0]?.url, "/api/v1/search?q=a");
  assert.equal(arranged.calls[0]?.init?.method, "GET");
  assert.equal(arranged.calls[0]?.init?.cache, "no-store");
});

test("401 is signed out", async () => {
  const { loaded } = await load("/api/v1/tools", () =>
    json(401, { code: "not_signed_in", message: "Sign in first." }),
  );
  assert.deepEqual(loaded, { kind: "signed_out" });
});

test("403 is denied, with the envelope's message when the reply carries one", async () => {
  const { loaded } = await load("/api/v1/tools", () =>
    json(403, { code: "not_owner", message: "Only the owner can see this." }),
  );
  assert.deepEqual(loaded, {
    kind: "denied",
    message: "Only the owner can see this.",
  });
  const { loaded: bare } = await load(
    "/api/v1/tools",
    () => new Response("<html>Forbidden</html>", { status: 403 }),
  );
  assert.deepEqual(bare, { kind: "denied", message: null });
});

test("404 and 422 are not found", async () => {
  for (const status of [404, 422]) {
    const { loaded } = await load("/api/v1/tools/nope", () =>
      json(status, { code: "not_found", message: "Not found." }),
    );
    assert.deepEqual(loaded, { kind: "not_found" }, `status ${status}`);
  }
});

test("a 5xx, any other refusal and a network failure are unavailable, with the status if any", async () => {
  for (const status of [500, 502, 503, 504, 409, 429]) {
    const { loaded } = await load("/api/v1/runs", () =>
      json(status, { code: "service_unavailable", message: "Down." }),
    );
    assert.deepEqual(loaded, { kind: "unavailable", status }, `${status}`);
  }
  const { loaded } = await load("/api/v1/runs", () => {
    throw new TypeError("Failed to fetch");
  });
  assert.deepEqual(loaded, { kind: "unavailable", status: null });
});

test("a refused reply's body is read, so its connection is released", async () => {
  for (const reply of [
    () => json(503, { code: "service_unavailable", message: "Down." }),
    () => new Response("<html>Bad Gateway</html>", { status: 502 }),
    () => json(403, { code: "not_owner", message: "No." }),
  ]) {
    const { arranged } = await load("/api/v1/runs", reply);
    assert.equal(arranged.replies[0]?.bodyUsed, true);
  }
});

test("a drifted reply is out of date, naming the schema and the field, never a value", async () => {
  const { loaded } = await load("/api/v1/search?q=private+words", () =>
    json(200, { schema_version: 1, query: "private words", results: "x" }),
  );
  assert.deepEqual(loaded, {
    kind: "out_of_date",
    schema: "SearchResults",
    path: "SearchResults.results",
  });
  assert.doesNotMatch(JSON.stringify(loaded), /private/);
});

test("a reply that isn't JSON is out of date, naming the route without its query", async () => {
  const { loaded } = await load(
    "/api/v1/search?q=private+words",
    () => new Response("<html>not it</html>", { status: 200 }),
  );
  assert.deepEqual(loaded, {
    kind: "out_of_date",
    schema: null,
    path: "/api/v1/search",
  });
});

test("reads of one path in flight together share one request, and nothing is kept after it settles", async () => {
  let release: (reply: Response) => void = () => undefined;
  const arranged = arrange(
    () =>
      new Promise<Response>((resolve) => {
        release = resolve;
      }),
  );
  const options = { fetch: arranged.fetch };
  const first = loadJson(
    "/api/v1/search?q=shared",
    parseSearchResults,
    options,
  );
  const second = loadJson(
    "/api/v1/search?q=shared",
    (value) => parseSearchResults(value).results.length,
    options,
  );
  assert.equal(readsInFlight(), 1);
  release(json(200, FOUND));
  // Each reader parses the shared body with its own parser.
  assert.deepEqual(await first, { kind: "ready", value: FOUND });
  assert.deepEqual(await second, { kind: "ready", value: 0 });
  assert.equal(arranged.calls.length, 1);
  assert.equal(readsInFlight(), 0);

  const later = arrange(() => json(200, FOUND));
  await loadJson("/api/v1/search?q=shared", parseSearchResults, {
    fetch: later.fetch,
  });
  assert.equal(later.calls.length, 1, "a settled read is asked for again");
  assert.equal(readsInFlight(), 0);
});

test("the shared request is aborted only when every reader has left", async () => {
  let signal: AbortSignal | undefined;
  const fetcher: typeof globalThis.fetch = (_input, init) =>
    new Promise<Response>((_resolve, reject) => {
      signal = init?.signal ?? undefined;
      signal?.addEventListener("abort", () => reject(signal?.reason));
    });
  const one = new AbortController();
  const two = new AbortController();
  const first = loadJson("/api/v1/runs?left", parseSearchResults, {
    fetch: fetcher,
    signal: one.signal,
  });
  const second = loadJson("/api/v1/runs?left", parseSearchResults, {
    fetch: fetcher,
    signal: two.signal,
  });
  one.abort();
  await first;
  assert.equal(signal?.aborted, false, "another reader still waits");
  assert.equal(readsInFlight(), 1);
  two.abort();
  await second;
  assert.equal(signal?.aborted, true);
  assert.equal(readsInFlight(), 0);
});

test("the log record of a mismatch carries the schema and path only", () => {
  const failure: LoadFailure = {
    kind: "out_of_date",
    schema: "RunList",
    path: "RunList.runs[0].status",
  };
  assert.deepEqual(mismatchRecord(failure), {
    event: "web.contract_mismatch",
    schema: "RunList",
    path: "RunList.runs[0].status",
  });
  assert.equal(mismatchRecord({ kind: "unavailable", status: 503 }), null);
});

test("each failure has fixed words, and only an unavailable read offers Retry", () => {
  assert.deepEqual(failureWords({ kind: "unavailable", status: 503 }, "runs"), {
    words:
      "Runs can't be read right now. Check that the local services are running, then try again.",
    retry: true,
  });
  assert.deepEqual(failureWords({ kind: "signed_out" }, "runs"), {
    words: "You're signed out. Sign in to see runs.",
    retry: false,
  });
  assert.deepEqual(
    failureWords({ kind: "denied", message: "Owners only." }, "runs"),
    { words: "Owners only.", retry: false },
  );
  assert.deepEqual(failureWords({ kind: "denied", message: null }, "runs"), {
    words: "You don't have access to runs.",
    retry: false,
  });
  assert.deepEqual(failureWords({ kind: "not_found" }, "this tool"), {
    words: "This tool can't be found.",
    retry: false,
  });
  assert.equal(
    OUT_OF_DATE,
    "This page and the local service disagree. Reload after updating.",
  );
  assert.deepEqual(
    failureWords({ kind: "out_of_date", schema: null, path: "/x" }, "runs"),
    { words: OUT_OF_DATE, retry: false },
  );
});

test("of several reads, the failure the person must act on first is shown", () => {
  const ready: Loaded<number> = { kind: "ready", value: 1 };
  const down: LoadFailure = { kind: "unavailable", status: 503 };
  assert.equal(worstFailure([ready, { kind: "loading" }, ready]), null);
  assert.deepEqual(worstFailure([down, ready]), down);
  assert.deepEqual(worstFailure([down, { kind: "signed_out" }]), {
    kind: "signed_out",
  });
  const outdated: LoadFailure = {
    kind: "out_of_date",
    schema: "RunList",
    path: "RunList.runs",
  };
  assert.deepEqual(worstFailure([{ kind: "not_found" }, outdated]), outdated);
});

test("polling backs off by doubling up to its cap", () => {
  assert.deepEqual(
    [1, 2, 3, 4, 5, 6].map((failures) => backoff(failures, 1000, 15_000)),
    [1000, 2000, 4000, 8000, 15_000, 15_000],
  );
  assert.equal(backoff(0, 1000, 15_000), 1000);
});
