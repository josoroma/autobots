/**
 * A person's run commands (R-49, WRUN-12): their words, their submit target, the body and the one
 * POST that sends them, and the version read before a press. Which commands a run offers comes from
 * the service, as RunWorkspace.allowed_commands, so nothing here derives it from a status.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import { forgetCsrfToken } from "../../lib/csrf-fetch.ts";
import {
  COMMAND_LABEL,
  commandBody,
  commandTarget,
  currentVersion,
  sendRunCommand,
} from "../../lib/runs/commands.ts";
import * as commands from "../../lib/runs/commands.ts";
import * as status from "../../lib/runs/status.ts";

const RUN = "11111111-1111-4111-8111-111111111111";

test("each command has its button's words", () => {
  assert.deepEqual(COMMAND_LABEL, {
    pause: "Pause",
    resume: "Resume",
    cancel: "Cancel run",
  });
});

test("Pause and Resume share the run as their target, and Cancel has its own", () => {
  // Decision 0027 D2: after a lost Pause, Resume sends nothing until a reload shows what applied,
  // and the lost Pause never holds back Cancel.
  assert.equal(commandTarget("pause"), "");
  assert.equal(commandTarget("resume"), "");
  assert.equal(commandTarget("cancel"), "cancel");
});

test("the body carries the version the sender means", () => {
  assert.equal(commandBody(7), '{"expected_version":7}');
});

test("a command is one POST to its route, with its key, body and write token", async () => {
  forgetCsrfToken();
  const sent: { url: string; init: RequestInit | undefined }[] = [];
  const real = globalThis.fetch;
  globalThis.fetch = async (input, init) => {
    const url = String(input);
    if (url === "/api/csrf")
      return new Response(
        JSON.stringify({ header: "x-autobots-csrf", token: "t1" }),
      );
    sent.push({ url, init });
    return new Response("{}");
  };
  try {
    await sendRunCommand(`${RUN}/x`, "pause", {
      key: "k1",
      body: commandBody(3),
    });
  } finally {
    globalThis.fetch = real;
    forgetCsrfToken();
  }
  assert.deepEqual(sent, [
    {
      url: `/api/v1/runs/${encodeURIComponent(`${RUN}/x`)}/pause`,
      init: {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": "k1",
          "x-autobots-csrf": "t1",
        },
        body: '{"expected_version":3}',
      },
    },
  ]);
});

const summary = (version: number) => ({
  schema_version: 1,
  version,
  id: RUN,
  workspace_id: "22222222-2222-4222-8222-222222222222",
  parent_run_id: null,
  status: "running",
  created_at: "2026-11-15T00:00:00+00:00",
  updated_at: "2026-11-15T00:00:00+00:00",
  budget: { spent_micro_usd: 0, reserved_micro_usd: 0, limit_micro_usd: 1 },
});

test("the version read before a press is the run's own, or the shown one when it can't be read", async () => {
  const asked: string[] = [];
  const reply =
    (body: unknown, status = 200): typeof globalThis.fetch =>
    async (input) => {
      asked.push(String(input));
      return new Response(JSON.stringify(body), {
        status,
        headers: { "content-type": "application/json" },
      });
    };
  assert.equal(await currentVersion(RUN, 2, { fetch: reply(summary(5)) }), 5);
  assert.deepEqual(asked, [`/api/v1/runs/${RUN}`]);
  assert.equal(
    await currentVersion(RUN, 2, {
      fetch: reply({ code: "service_unavailable", message: "x" }, 503),
    }),
    2,
  );
  assert.equal(
    await currentVersion(RUN, 2, { fetch: reply({ version: "5" }) }),
    2,
  );
  const offline: typeof globalThis.fetch = async () => {
    throw new TypeError("offline");
  };
  assert.equal(await currentVersion(RUN, 2, { fetch: offline }), 2);
});

test("the commands a run offers come from the service, never from a status here", () => {
  assert.equal("commandsFor" in commands, false);
  assert.equal("commandsFor" in status, false);
});
