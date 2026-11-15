/**
 * The browser's client (R-48): calls go through the BFF's same-origin routes with the generated
 * operations, a write carries the double-submit token and its Idempotency-Key, the routes
 * PRD-Model-Providers MP-05 names keep their names, and a failure is told by its status and
 * envelope.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  admitRun,
  getModels,
  parseWorkflowView,
  resetModelPolicyOverrides,
  validateOpenRouter,
} from "@autobots/api-client";
import { ContractError, HttpFailure } from "@autobots/api-client/runtime";

import {
  bffUrl,
  chooseWorkspace,
  failureOf,
  signIn,
  signOut,
  writeAsTyped,
  writes,
} from "../../lib/api/browser.ts";
import { forgetCsrfToken } from "../../lib/csrf-fetch.ts";
import { load, readOf } from "../../lib/load.ts";

interface Sent {
  url: string;
  method: string | undefined;
  headers: Record<string, string>;
  body: unknown;
}

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status });
const refused = () => json(409, { code: "conflict", message: "It changed." });

/** Runs `call` against an arranged BFF, and returns what it sent, besides the token fetch. */
async function sending(
  reply: () => Response,
  call: () => Promise<unknown>,
): Promise<{ sent: Sent[]; outcome: unknown }> {
  forgetCsrfToken();
  const sent: Sent[] = [];
  const real = globalThis.fetch;
  globalThis.fetch = async (input, init) => {
    const url = String(input);
    if (url === "/api/csrf") {
      return json(200, { header: "x-autobots-csrf", token: "t1" });
    }
    const body = init?.body;
    sent.push({
      url,
      method: init?.method,
      headers: Object.fromEntries(new Headers(init?.headers).entries()),
      body: typeof body === "string" ? JSON.parse(body) : body,
    });
    return reply();
  };
  try {
    const outcome = await call().then(
      (value) => value,
      (error: unknown) => error,
    );
    return { sent, outcome };
  } finally {
    globalThis.fetch = real;
    forgetCsrfToken();
  }
}

test("a write goes to the BFF's route with its body, the write token and its Idempotency-Key", async () => {
  const { sent, outcome } = await sending(refused, () =>
    admitRun(writes, { goal_text: "Count" }, { "Idempotency-Key": "k1" }),
  );
  assert.ok(outcome instanceof HttpFailure);
  assert.deepEqual(sent, [
    {
      url: "/api/v1/runs",
      method: "POST",
      headers: {
        "content-type": "application/json",
        "idempotency-key": "k1",
        "x-autobots-csrf": "t1",
      },
      body: { goal_text: "Count" },
    },
  ]);
});

test("the routes PRD-Model-Providers MP-05 names keep their names", async () => {
  const { sent } = await sending(refused, () =>
    resetModelPolicyOverrides(writes, { expected_version: 7 }),
  );
  assert.equal(sent[0]?.url, "/api/settings/model-policy/reset");
  const asked: string[] = [];
  await load(readOf(getModels), {
    fetch: async (input) => {
      asked.push(String(input));
      return refused();
    },
  });
  assert.deepEqual(asked, ["/api/models"]);
  assert.equal(bffUrl("/api/v1/models"), "/api/models");
  assert.equal(
    bffUrl("/api/v1/settings/keys-and-vars/A_KEY"),
    "/api/settings/keys-and-vars/A_KEY",
  );
  for (const unchanged of ["/api/v1/modelsx", "/api/v1/runs", "/api/csrf"]) {
    assert.equal(bffUrl(unchanged), unchanged);
  }
});

test("a write without a body sends neither a body nor a content type", async () => {
  const { sent } = await sending(refused, () => validateOpenRouter(writes));
  assert.deepEqual(sent, [
    {
      url: "/api/settings/model-providers/openrouter/validate",
      method: "POST",
      headers: { "x-autobots-csrf": "t1" },
      body: undefined,
    },
  ]);
});

test("a failure has a status and envelope only when a reply refused the call", () => {
  const envelope = { code: "conflict", message: "It changed." };
  assert.deepEqual(failureOf(new HttpFailure("/v1/runs", 409, envelope)), {
    status: 409,
    refusal: envelope,
  });
  assert.deepEqual(failureOf(new HttpFailure("/v1/runs", 502, null)), {
    status: 502,
    refusal: null,
  });
  for (const error of [
    new ContractError("RunAccepted.run_id", "required"),
    new TypeError("Failed to fetch"),
  ]) {
    assert.deepEqual(failureOf(error), { status: null, refusal: null });
  }
});

test("signing in and out and choosing a workspace use the BFF's own routes, and parse its replies", async () => {
  const signedIn = await sending(
    () => json(200, { signed_in: true }),
    () => signIn({ email: "a@example.test", password: "pw" }),
  );
  assert.deepEqual(signedIn.outcome, { signed_in: true });
  assert.equal(signedIn.sent[0]?.url, "/api/session");
  assert.equal(signedIn.sent[0]?.method, "POST");
  assert.deepEqual(signedIn.sent[0]?.body, {
    email: "a@example.test",
    password: "pw",
  });

  const wrong = await sending(
    () => json(401, { code: "sign_in_failed", message: "No." }),
    () => signIn({ email: "a@example.test", password: "pw" }),
  );
  assert.equal(failureOf(wrong.outcome).status, 401);

  const out = await sending(() => json(200, { signed_in: false }), signOut);
  assert.deepEqual(out.outcome, { signed_in: false });
  assert.deepEqual(out.sent[0], {
    url: "/api/session",
    method: "DELETE",
    headers: { "x-autobots-csrf": "t1" },
    body: undefined,
  });

  const chosen = await sending(
    () => json(200, {}),
    () => chooseWorkspace({ workspace_id: "w1" }),
  );
  assert.equal(chosen.sent[0]?.url, "/api/workspace");
  assert.deepEqual(chosen.sent[0]?.body, { workspace_id: "w1" });
  assert.ok(chosen.outcome instanceof ContractError, "a drifted reply");
});

test("JSON a person typed is sent as typed to its operation's route, with its key", async () => {
  const typed = { expected_version: 1, graph: "not a graph" };
  const { sent, outcome } = await sending(
    () => json(422, { code: "invalid_request", message: "Not valid." }),
    () =>
      writeAsTyped(
        { method: "POST", path: "/v1/workflows/w1/versions" },
        typed,
        parseWorkflowView,
        "k1",
      ),
  );
  assert.equal(failureOf(outcome).refusal?.code, "invalid_request");
  assert.deepEqual(sent, [
    {
      url: "/api/v1/workflows/w1/versions",
      method: "POST",
      headers: {
        "content-type": "application/json",
        "idempotency-key": "k1",
        "x-autobots-csrf": "t1",
      },
      body: typed,
    },
  ]);
});
