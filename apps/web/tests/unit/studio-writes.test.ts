/**
 * Pins the Studio's shared write words and bodies (WBLD-09, R-59): a session's body and its reply's
 * words, which the Experts list and the Expert editor share, and a create's reply's words, which the
 * Experts and Workflows lists share (Decision 0027 D2).
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  CREATE_LOST,
  createText,
  SESSION_LOST,
  SESSION_REFUSED,
  sessionBody,
  sessionText,
} from "../../lib/studio-writes.ts";
import { HELD_NOTE } from "../../lib/submit.ts";

const REFUSALS = { name_taken: "That name is already used." };

test("a session names each Expert it starts with", () => {
  assert.deepEqual(sessionBody("direct", ["e-1"]), {
    kind: "direct",
    experts: [{ expert_id: "e-1" }],
  });
  assert.deepEqual(sessionBody("coordinator", ["e-1", "e-2"]), {
    kind: "coordinator",
    experts: [{ expert_id: "e-1" }, { expert_id: "e-2" }],
  });
});

test("a session that didn't start says whether it may have", () => {
  assert.equal(sessionText({ outcome: "unknown", held: true }), SESSION_LOST);
  assert.equal(
    sessionText({ outcome: "refused", held: false }),
    SESSION_REFUSED,
  );
  assert.equal(
    sessionText({ outcome: "refused", held: true }),
    `${SESSION_REFUSED} ${HELD_NOTE}`,
  );
  assert.equal(
    SESSION_LOST,
    "The reply was lost, so the session may have started. Pressing again won't start a second one.",
  );
});

test("a create that didn't open its item says why, from the screen's table", () => {
  const reply = (
    outcome: "refused" | "unknown",
    code: string | null,
    held = false,
  ) => ({
    outcome,
    refusal: code === null ? null : { code, message: "not shown" },
    held,
  });
  assert.equal(createText(reply("unknown", null), REFUSALS), CREATE_LOST);
  assert.equal(
    createText(reply("refused", "name_taken"), REFUSALS),
    "That name is already used.",
  );
  assert.equal(
    createText(reply("refused", "other"), REFUSALS),
    "That could not be saved.",
  );
  assert.equal(
    createText(reply("refused", null), REFUSALS),
    "That could not be saved.",
  );
  assert.equal(
    createText(reply("refused", "name_taken", true), REFUSALS),
    `That name is already used. ${HELD_NOTE}`,
  );
  assert.equal(
    CREATE_LOST,
    "The reply was lost, so it may have been created. Pressing again won't create a second one.",
  );
});
