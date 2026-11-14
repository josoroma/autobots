import assert from "node:assert/strict";
import { test } from "node:test";

import {
  changedChoice,
  changesChoice,
  HELD_NOTE,
  heldFor,
  keeps,
  labelOf,
  nextAttempt,
  outcomeOf,
  refusalText,
  settle,
  withHeld,
  type Holds,
} from "../../lib/submit.ts";

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

test("a new intent gets a new key, and a held one is resent as it was", () => {
  let minted = 0;
  const mint = () => `key-${++minted}`;
  const first = nextAttempt(null, '{"goal_text":"a"}', mint);
  assert.deepEqual(first, {
    key: "key-1",
    body: '{"goal_text":"a"}',
    scope: "",
    choice: "",
  });
  // The draft changed, but the first write's outcome is unknown, so it's resent unchanged.
  assert.deepEqual(nextAttempt(first, '{"goal_text":"b"}', mint), first);
  assert.equal(minted, 1);
  assert.equal(nextAttempt(null, null, mint), null);
});

test("only an accepted reply settles a held write", () => {
  // A first press: a refusal or an acceptance settles it, and only an unknown reply holds it.
  assert.equal(keeps("accepted", false), false);
  assert.equal(keeps("refused", false), false);
  assert.equal(keeps("unknown", false), true);
  // Unknown, then refused: the refusal may have come before the key was looked at, such as an
  // expired session or a budget the first run reserved, so the next press resends the same key.
  assert.equal(keeps("refused", true), true);
  assert.equal(keeps("unknown", true), true);
  assert.equal(keeps("accepted", true), false);
});

test("unknown, then refused, then pressed again resends the same key", () => {
  let minted = 0;
  const mint = () => `key-${++minted}`;
  const first = nextAttempt(null, '{"continues_run_id":"r"}', mint);
  assert.ok(first !== null);
  let held = keeps("unknown", false) ? first : null;
  const second = nextAttempt(held, '{"continues_run_id":"r"}', mint);
  held = keeps("refused", second === held) ? second : null;
  assert.equal(nextAttempt(held, "{}", mint)?.key, "key-1");
  assert.equal(minted, 1);
});

test("another choice on a held target is refused, and the same choice is resent", () => {
  let minted = 0;
  const mint = () => `key-${++minted}`;
  const approve = nextAttempt(
    null,
    '{"decision":"approve"}',
    mint,
    "approval-1",
    "approve",
  );
  assert.equal(changesChoice(approve, "reject"), true);
  assert.equal(changesChoice(approve, "approve"), false);
  assert.equal(changesChoice(null, "reject"), false);
});

test("a refusal of a resent write says the first press may have gone through", () => {
  assert.equal(withHeld("Budget reached.", false), "Budget reached.");
  assert.equal(
    withHeld("Budget reached.", true),
    `Budget reached. ${HELD_NOTE}`,
  );
});

test("a changed choice names the held one, and says nothing was sent", () => {
  const text = changedChoice("Approve");
  assert.match(text, /^Nothing was sent\./);
  assert.match(text, /"Approve"/);
  assert.match(text, /Reload/);
});

test("a refusal reads from the screen's table, then the service, and no refusal is a lost reply", () => {
  const table = { stale_version: "Reload, then try again." };
  const lost = "The reply was lost.";
  assert.equal(
    refusalText(table, { code: "stale_version", message: "x" }, lost),
    "Reload, then try again.",
  );
  assert.equal(
    refusalText(
      table,
      { code: "other", message: "The service's words." },
      lost,
    ),
    "The service's words.",
  );
  assert.equal(refusalText(table, null, lost), lost);
});

test("the hook's holds: one per target, settled only by an accepted reply, and untouched by unkeyed writes", () => {
  let minted = 0;
  const mint = () => `key-${++minted}`;
  let holds: Holds = new Map();
  // A lost Pause holds the run.
  const pause = nextAttempt(null, '{"expected_version":3}', mint, "", "pause");
  assert.ok(pause !== null);
  holds = settle(holds, pause, "unknown", false, true);
  // Resume on the same run sends nothing.
  assert.deepEqual(heldFor(holds, "", "resume", true), {
    changed: true,
    held: pause,
  });
  // Pause again resends the same key, and a refusal of that resend keeps it.
  const again = heldFor(holds, "", "pause", true);
  assert.equal(again.changed, false);
  assert.equal(nextAttempt(again.held, "{}", mint, "", "pause")?.key, "key-1");
  holds = settle(holds, pause, "refused", true, true);
  assert.equal(holds.get("")?.key, "key-1");
  // Another target's reply leaves this hold alone.
  const other = nextAttempt(null, "{}", mint, "approval-2", "approve");
  assert.ok(other !== null);
  holds = settle(holds, other, "accepted", false, true);
  assert.equal(holds.get("")?.key, "key-1");
  // An unkeyed write on the same target neither resends nor clears it.
  assert.deepEqual(heldFor(holds, "", "", false), {
    changed: false,
    held: null,
  });
  const save = nextAttempt(null, '{"graph":{}}', mint, "", "");
  assert.ok(save !== null);
  assert.equal(settle(holds, save, "accepted", false, false), holds);
  // Only an accepted reply settles it.
  holds = settle(holds, pause, "accepted", true, true);
  assert.equal(holds.size, 0);
});

test("an unkeyed write sends the latest body after a lost reply", () => {
  let minted = 0;
  const mint = () => `key-${++minted}`;
  let holds: Holds = new Map();
  const first = nextAttempt(null, '{"graph":"a"}', mint);
  assert.ok(first !== null);
  holds = settle(holds, first, "unknown", false, false);
  const { held } = heldFor(holds, "", "", false);
  assert.equal(nextAttempt(held, '{"graph":"b"}', mint)?.body, '{"graph":"b"}');
});

test("a held choice is named by its button, or generically", () => {
  const labels = { pause: "Pause", cancel: "Cancel run" };
  assert.equal(labelOf(labels, "cancel"), "Cancel run");
  assert.equal(labelOf(labels, "other"), "your first choice");
  assert.equal(labelOf(labels, null), "your first choice");
});
