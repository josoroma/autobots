/**
 * The workflow writes that send JSON a person typed name their routes by hand (R-48), so each is
 * checked against its generated operation: a renamed route or method fails here rather than in the
 * browser.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  createWorkflowExecution,
  publishWorkflowVersion,
  saveWorkflowDraft,
  validateWorkflow,
} from "@autobots/api-client";
import type { ClientOptions } from "@autobots/api-client/runtime";

import {
  draftRoute,
  executionRoute,
  publishRoute,
  VALIDATE_ROUTE,
} from "../../lib/workflows/unchecked-writes.ts";

/** The method and route a generated operation asks for. */
async function requested(
  call: (client: ClientOptions) => Promise<unknown>,
): Promise<{ method: string | undefined; path: string } | undefined> {
  const seen: { method: string | undefined; path: string }[] = [];
  await call({
    baseUrl: "",
    fetch: async (input, init) => {
      seen.push({ method: init?.method, path: String(input) });
      return new Response("{}", { status: 503 });
    },
  }).catch(() => undefined);
  return seen[0];
}

// An identifier that has to be encoded, so a route that skips the encoding fails too.
const ID = "w 1/x";
const KEY = { "Idempotency-Key": "k1" };

test("each typed write's route is its generated operation's method and route", async () => {
  assert.deepEqual(
    await requested((client) => validateWorkflow(client, {})),
    VALIDATE_ROUTE,
  );
  assert.deepEqual(
    await requested((client) =>
      publishWorkflowVersion(
        client,
        ID,
        { expected_version: 1, graph: {} },
        KEY,
      ),
    ),
    publishRoute(ID),
  );
  assert.deepEqual(
    await requested((client) => saveWorkflowDraft(client, ID, { graph: {} })),
    draftRoute(ID),
  );
  assert.deepEqual(
    await requested((client) =>
      createWorkflowExecution(client, ID, { version: 1 }, KEY),
    ),
    executionRoute(ID),
  );
});
