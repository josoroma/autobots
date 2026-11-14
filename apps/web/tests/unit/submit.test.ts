import assert from "node:assert/strict";
import { test } from "node:test";

import { nextAttempt, outcomeOf } from "../../lib/submit.ts";

test("a parsed 2xx is accepted, and a 4xx with the envelope is refused", () => {
  assert.equal(outcomeOf(202, true, false), "accepted");
  assert.equal(outcomeOf(409, false, true), "refused");
  assert.equal(outcomeOf(422, false, true), "refused");
});

test("no reply, a 5xx, a proxy page or a 2xx that didn't parse is unknown", () => {
  assert.equal(outcomeOf(null, false, false), "unknown");
  assert.equal(outcomeOf(500, false, true), "unknown");
  assert.equal(outcomeOf(502, false, false), "unknown");
  assert.equal(outcomeOf(403, false, false), "unknown");
  assert.equal(outcomeOf(202, false, false), "unknown");
});

test("a new intent gets a new key, and an unknown one is resent as it was", () => {
  let minted = 0;
  const mint = () => `key-${++minted}`;
  const first = nextAttempt(null, '{"goal_text":"a"}', mint);
  assert.deepEqual(first, { key: "key-1", body: '{"goal_text":"a"}' });
  // The draft changed, but the first write's outcome is unknown, so it's resent unchanged.
  assert.deepEqual(nextAttempt(first, '{"goal_text":"b"}', mint), first);
  assert.equal(minted, 1);
  assert.equal(nextAttempt(null, null, mint), null);
});
