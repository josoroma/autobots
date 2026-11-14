import assert from "node:assert/strict";
import { test } from "node:test";

import { parseRunAccepted } from "@autobots/api-client";

import { readErrorResponse, readReply } from "../../lib/replies.ts";

const RUN = "11111111-1111-4111-8111-111111111111";

test("a refusal body is the service's envelope", async () => {
  const reply = new Response(
    JSON.stringify({ code: "budget_too_high", message: "Lower it." }),
    { status: 409 },
  );
  assert.deepEqual(await readErrorResponse(reply), {
    code: "budget_too_high",
    message: "Lower it.",
  });
});

test("an HTML page, a stranger body or no reply is not an envelope", async () => {
  for (const reply of [
    new Response("<html>Bad Gateway</html>", { status: 502 }),
    new Response(JSON.stringify({ detail: "x" }), { status: 422 }),
    new Response("", { status: 503 }),
    null,
  ]) {
    assert.equal(await readErrorResponse(reply), null);
  }
});

test("an accepted run is parsed", async () => {
  const body = {
    schema_version: 1,
    run_id: RUN,
    status: "queued",
    version: 1,
    replayed: false,
  };
  assert.deepEqual(
    await readReply(
      new Response(JSON.stringify(body), { status: 202 }),
      parseRunAccepted,
    ),
    body,
  );
});

test("a reply without run_id, or not JSON, is null rather than /runs/undefined", async () => {
  const drifted = {
    schema_version: 1,
    id: RUN,
    status: "queued",
    version: 1,
    replayed: false,
  };
  assert.equal(
    await readReply(
      new Response(JSON.stringify(drifted), { status: 202 }),
      parseRunAccepted,
    ),
    null,
  );
  assert.equal(
    await readReply(
      new Response("accepted", { status: 202 }),
      parseRunAccepted,
    ),
    null,
  );
});
