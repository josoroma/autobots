import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import {
  getRun,
  parseErrorResponse,
  parseJobsChart,
  parseModelPolicyState,
  parseModelPolicyUpdate,
  parseRunEvent,
  parseRunRequest,
  parseRunSummary,
  parseSessionCreate,
  parseWorkflowGraph,
} from "../src/generated.ts";
import {
  ContractError,
  HttpFailure,
  parseWith,
  requestJson,
} from "../src/runtime.ts";

const parsers = {
  RunSummary: parseRunSummary,
  RunEvent: parseRunEvent,
  ErrorResponse: parseErrorResponse,
  WorkflowGraph: parseWorkflowGraph,
  ModelPolicyState: parseModelPolicyState,
  ModelPolicyUpdate: parseModelPolicyUpdate,
  JobsChart: parseJobsChart,
  RunRequest: parseRunRequest,
  SessionCreate: parseSessionCreate,
};

interface BoundaryCase {
  name: string;
  model: keyof typeof parsers;
  valid: boolean;
  value: unknown;
}

const cases: BoundaryCase[] = JSON.parse(
  readFileSync(
    new URL("../../../contracts/fixtures/boundary-cases.json", import.meta.url),
    "utf8",
  ),
);

for (const item of cases) {
  test(`shared boundary case: ${item.name}`, () => {
    const parse = parsers[item.model];
    if (item.valid) {
      assert.deepEqual(parse(item.value), item.value);
    } else {
      assert.throws(() => parse(item.value), ContractError);
    }
  });
}

test("a cast cannot stand in for validation", () => {
  const notARun = { id: "x" } as unknown;
  assert.throws(() => parseRunSummary(notARun), ContractError);
});

test("a response that fails its contract is refused by the client path", async () => {
  const options = {
    baseUrl: "http://fixture",
    fetch: async () => new Response(JSON.stringify({ id: "x" })),
  };
  const body = await requestJson(options, "GET", "/v1/runs/1");
  assert.throws(() => parseRunSummary(body), ContractError);
});

// R-02: a refusal is an HTTP failure with the service's envelope, and only a shape mismatch is drift.
function replying(response: () => Response) {
  return { baseUrl: "http://fixture", fetch: async () => response() };
}

test("a refusal is an HTTP failure that carries the envelope", async () => {
  const options = replying(
    () =>
      new Response(
        JSON.stringify({ code: "run_conflict", message: "It changed." }),
        { status: 409 },
      ),
  );
  await assert.rejects(getRun(options, "1"), (error: unknown) => {
    assert.ok(error instanceof HttpFailure);
    assert.equal(error.status, 409);
    assert.deepEqual(error.envelope, {
      code: "run_conflict",
      message: "It changed.",
    });
    return true;
  });
});

test("a failure without an envelope is still an HTTP failure, not drift", async () => {
  for (const body of ["Bad Gateway", JSON.stringify({ detail: "x" }), ""]) {
    await assert.rejects(
      getRun(
        replying(() => new Response(body, { status: 503 })),
        "1",
      ),
      (error: unknown) => {
        assert.ok(
          error instanceof HttpFailure && !(error instanceof ContractError),
        );
        assert.equal(error.status, 503);
        assert.equal(error.envelope, null);
        return true;
      },
    );
  }
});

test("a success that drifts from its contract is a contract error", async () => {
  await assert.rejects(
    getRun(
      replying(() => new Response(JSON.stringify({ id: "x" }))),
      "1",
    ),
    ContractError,
  );
  await assert.rejects(
    getRun(
      replying(() => new Response("not json")),
      "1",
    ),
    ContractError,
  );
});

test("a call can add headers and an abort signal", async () => {
  let seen: RequestInit | undefined;
  const options = {
    baseUrl: "http://fixture",
    headers: { "X-Base": "1" },
    fetch: async (_input: string | URL | Request, init?: RequestInit) => {
      seen = init;
      return new Response(JSON.stringify({ code: "x", message: "y" }), {
        status: 404,
      });
    },
  };
  const controller = new AbortController();
  await assert.rejects(
    getRun(options, "1", {
      headers: { "X-Call": "2" },
      signal: controller.signal,
    }),
    HttpFailure,
  );
  assert.deepEqual(seen?.headers, { "X-Base": "1", "X-Call": "2" });
  assert.equal(seen?.signal, controller.signal);
});

test("an unknown schema is an error", () => {
  assert.throws(() => parseWith({}, "Missing", {}), ContractError);
});

test("a date field is checked as a date", () => {
  const schemas = { Day: { type: "string", format: "date" } } as const;
  assert.equal(parseWith(schemas, "Day", "2026-11-14"), "2026-11-14");
  for (const value of ["2026-11-14T00:00:00Z", "14/11/2026", "2026-13-01"]) {
    assert.throws(() => parseWith(schemas, "Day", value), ContractError);
  }
});
