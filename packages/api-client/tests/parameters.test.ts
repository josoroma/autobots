/**
 * The generated query and header parameters (R-48). A read's query is written in the contract's
 * order and leaves out what wasn't given, and a write's declared Idempotency-Key reaches the
 * request. The headers the BFF sets from the session aren't parameters.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  admitRun,
  listRuns,
  listRunToolUses,
  search,
  type AdmitRunHeaders,
  type ListRunsQuery,
} from "../src/generated.ts";
import {
  ContractError,
  HttpFailure,
  queryString,
  type ClientOptions,
} from "../src/runtime.ts";

interface Sent {
  url: string;
  init: RequestInit | undefined;
}

/** A client that records what it sends and answers each request with `reply`. */
function recording(reply: () => Response): {
  options: ClientOptions;
  sent: Sent[];
} {
  const sent: Sent[] = [];
  return {
    sent,
    options: {
      baseUrl: "http://fixture",
      headers: { "X-Base": "1" },
      fetch: async (input, init) => {
        sent.push({ url: String(input), init });
        return reply();
      },
    },
  };
}

const refused = () =>
  new Response(JSON.stringify({ code: "not_found", message: "Gone." }), {
    status: 404,
  });

// True when a parameter can be left out, checked by tsc (api_client_typecheck).
type Optional<T> = undefined extends T ? true : false;

test("a query is written in the contract's order, and what wasn't given is left out", async () => {
  const { options, sent } = recording(refused);
  const query: ListRunsQuery = {
    profile: "openrouter_sol",
    q: "fully reported",
    group: "needs_you",
  };
  await assert.rejects(listRuns(options, query), HttpFailure);
  await assert.rejects(listRuns(options), HttpFailure);
  await assert.rejects(
    listRuns(options, { q: undefined, cursor: null }),
    HttpFailure,
  );
  assert.deepEqual(
    sent.map((item) => item.url),
    [
      "http://fixture/v1/runs?group=needs_you&q=fully+reported&profile=openrouter_sol",
      "http://fixture/v1/runs",
      "http://fixture/v1/runs",
    ],
  );
});

test("a number in the query is written as a decimal, after the path's own parameters", async () => {
  const { options, sent } = recording(refused);
  await assert.rejects(
    listRunToolUses(options, "run 1", { after: 3, limit: 200 }),
    HttpFailure,
  );
  assert.equal(
    sent[0]?.url,
    "http://fixture/v1/runs/run%201/tool-uses?after=3&limit=200",
  );
});

test("a required query must be passed, and its value is encoded", async () => {
  const searchNeedsItsQuery: Optional<Parameters<typeof search>[1]> = false;
  const runsQueryIsOptional: Optional<Parameters<typeof listRuns>[1]> = true;
  assert.equal(searchNeedsItsQuery, false);
  assert.equal(runsQueryIsOptional, true);
  const { options, sent } = recording(refused);
  await assert.rejects(search(options, { q: "a&b=c" }), HttpFailure);
  assert.equal(sent[0]?.url, "http://fixture/v1/search?q=a%26b%3Dc");
});

test("a declared Idempotency-Key reaches the request, beside the client's and the call's headers", async () => {
  const keyIsRequired: Optional<Parameters<typeof admitRun>[2]> = false;
  assert.equal(keyIsRequired, false);
  const { options, sent } = recording(refused);
  const headers: AdmitRunHeaders = { "Idempotency-Key": "k1" };
  await assert.rejects(
    admitRun(options, { goal_text: "Count" }, headers, {
      headers: { "X-Call": "2" },
    }),
    HttpFailure,
  );
  assert.equal(sent[0]?.url, "http://fixture/v1/runs");
  assert.equal(sent[0]?.init?.method, "POST");
  assert.equal(sent[0]?.init?.body, JSON.stringify({ goal_text: "Count" }));
  assert.deepEqual(sent[0]?.init?.headers, {
    "Content-Type": "application/json",
    "X-Base": "1",
    "X-Call": "2",
    "Idempotency-Key": "k1",
  });
});

test("a call's own headers can't replace a declared one", async () => {
  const { options, sent } = recording(refused);
  await assert.rejects(
    admitRun(
      options,
      {},
      { "Idempotency-Key": "k1" },
      { headers: { "Idempotency-Key": "k2" } },
    ),
    HttpFailure,
  );
  assert.deepEqual(sent[0]?.init?.headers, {
    "Content-Type": "application/json",
    "X-Base": "1",
    "Idempotency-Key": "k1",
  });
});

test("a reply that isn't JSON names the route, never its query", async () => {
  const { options } = recording(() => new Response("not json"));
  await assert.rejects(
    listRuns(options, { q: "what a person typed" }),
    (error: unknown) => {
      assert.ok(error instanceof ContractError);
      assert.equal(error.path, "/v1/runs");
      return true;
    },
  );
});

test("the query string keeps the given order, and skips null, undefined and undeclared names", () => {
  assert.equal(queryString(undefined, ["a"]), "");
  assert.equal(queryString({}, ["a"]), "");
  assert.equal(
    queryString({ b: 2, a: "x y", c: null, d: undefined, e: "no" }, [
      "a",
      "b",
      "c",
      "d",
    ]),
    "?a=x+y&b=2",
  );
  assert.equal(queryString({ on: true }, ["on"]), "?on=true");
});
