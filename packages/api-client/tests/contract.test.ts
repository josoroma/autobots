import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { parseErrorResponse, parseRunEvent, parseRunSummary, parseWorkflowGraph } from "../src/generated.ts";
import { ContractError, parseWith, requestJson } from "../src/runtime.ts";

const cases = JSON.parse(readFileSync(new URL("../../../contracts/fixtures/boundary-cases.json", import.meta.url), "utf8"));
const parsers = { RunSummary: parseRunSummary, RunEvent: parseRunEvent, ErrorResponse: parseErrorResponse, WorkflowGraph: parseWorkflowGraph };

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
  const options = { baseUrl: "http://fixture", fetch: async () => new Response(JSON.stringify({ id: "x" })) };
  const body = await requestJson(options, "GET", "/v1/runs/1");
  assert.throws(() => parseRunSummary(body), ContractError);
});

test("a failed request is an error, not a parsed body", async () => {
  const options = { baseUrl: "http://fixture", fetch: async () => new Response("{}", { status: 500 }) };
  await assert.rejects(requestJson(options, "GET", "/v1/runs/1"), ContractError);
});

test("an unknown schema is an error", () => {
  assert.throws(() => parseWith({}, "Missing", {}), ContractError);
});
