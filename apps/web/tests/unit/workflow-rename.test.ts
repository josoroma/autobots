/**
 * Pins what the editor's name field sends and says (Decision 0037 N2, US-19.1): the name trimmed,
 * nothing for a blank one, the refusals in the screen's words, and the generated write's route.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import { renameWorkflow } from "@autobots/api-client";

import {
  BLANK_NAME,
  NAME_LOST,
  NAME_MAX,
  NAME_NOT_SAVED,
  nameToSend,
  renameRefusal,
} from "../../lib/workflows/rename.ts";

test("a name is sent trimmed, and a blank one isn't sent", () => {
  assert.equal(nameToSend("  Monthly FX note  "), "Monthly FX note");
  assert.equal(nameToSend("Monthly FX note"), "Monthly FX note");
  assert.equal(nameToSend(""), null);
  assert.equal(nameToSend("   "), null);
  assert.equal(BLANK_NAME, "A workflow needs a name.");
});

test("the field keeps creation's longest name", () => {
  assert.equal(NAME_MAX, 100);
});

test("a refused rename is said in the screen's words", () => {
  assert.equal(
    renameRefusal("refused", "workflow_name_taken"),
    "That name is already used.",
  );
  assert.equal(
    renameRefusal("refused", "owner_required"),
    "Only the workspace owner can rename a workflow.",
  );
  assert.equal(renameRefusal("refused", "invalid_request"), NAME_NOT_SAVED);
  assert.equal(renameRefusal("refused"), NAME_NOT_SAVED);
  assert.equal(renameRefusal("unknown", "workflow_name_taken"), NAME_LOST);
});

test("the rename is a PUT to the workflow's name, with no key", async () => {
  const seen: {
    method: string | undefined;
    path: string;
    key: string | null;
  }[] = [];
  await renameWorkflow(
    {
      baseUrl: "",
      fetch: async (input, init) => {
        seen.push({
          method: init?.method,
          path: String(input),
          key: new Headers(init?.headers).get("Idempotency-Key"),
        });
        return new Response("{}", { status: 503 });
      },
    },
    "w 1/x",
    { name: "Monthly FX note" },
  ).catch(() => undefined);
  assert.deepEqual(seen, [
    { method: "PUT", path: "/v1/workflows/w%201%2Fx/name", key: null },
  ]);
});
