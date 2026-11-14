import assert from "node:assert/strict";
import { test } from "node:test";

import { ARM_MS, chord, press, type Arm } from "../../lib/approval-shortcut.ts";

const keys = { metaKey: false, ctrlKey: false, altKey: false };
const first = {
  decision: "approve" as const,
  approvalId: "a",
  truncated: false,
  repeat: false,
  now: 1_000,
};
const armed: Arm = {
  decision: "approve",
  approvalId: "a",
  until: 1_000 + ARM_MS,
};

test("⌘ or Ctrl with Enter approves, and with Backspace rejects", () => {
  assert.equal(chord({ ...keys, key: "Enter", metaKey: true }), "approve");
  assert.equal(chord({ ...keys, key: "Enter", ctrlKey: true }), "approve");
  assert.equal(chord({ ...keys, key: "Backspace", metaKey: true }), "reject");
  assert.equal(chord({ ...keys, key: "Backspace", ctrlKey: true }), "reject");
});

test("an Alt chord, a bare key or another key is not a shortcut", () => {
  assert.equal(chord({ ...keys, key: "Enter", altKey: true }), null);
  assert.equal(
    chord({ ...keys, key: "Enter", metaKey: true, altKey: true }),
    null,
  );
  assert.equal(
    chord({ ...keys, key: "Backspace", ctrlKey: true, altKey: true }),
    null,
  );
  assert.equal(chord({ ...keys, key: "Enter" }), null);
  assert.equal(chord({ ...keys, key: "j", metaKey: true }), null);
});

test("the first press arms the selected request for 2 seconds", () => {
  assert.deepEqual(press(null, first), { kind: "arm", arm: armed });
});

test("a second press of the same chord on the same request within 2 s decides", () => {
  assert.deepEqual(press(armed, { ...first, now: 1_000 + ARM_MS }), {
    kind: "decide",
    decision: "approve",
  });
});

test("a held key's repeated keydown is ignored, armed or not", () => {
  assert.deepEqual(press(armed, { ...first, repeat: true, now: 1_050 }), {
    kind: "ignore",
  });
  assert.deepEqual(press(null, { ...first, repeat: true }), { kind: "ignore" });
});

test("an arm never carries over to another request", () => {
  assert.deepEqual(press(armed, { ...first, approvalId: "b", now: 1_500 }), {
    kind: "arm",
    arm: { decision: "approve", approvalId: "b", until: 1_500 + ARM_MS },
  });
});

test("the other decision, or a press after 2 s, arms again instead of deciding", () => {
  assert.equal(
    press(armed, { ...first, decision: "reject", now: 1_500 }).kind,
    "arm",
  );
  assert.equal(press(armed, { ...first, now: 1_001 + ARM_MS }).kind, "arm");
});

test("a request too long to show whole can't be approved, but can be rejected", () => {
  assert.deepEqual(press(armed, { ...first, truncated: true }), {
    kind: "too_large",
  });
  const rejecting = { ...first, decision: "reject" as const, truncated: true };
  const arm = press(null, rejecting);
  assert.equal(arm.kind, "arm");
  if (arm.kind === "arm") {
    assert.deepEqual(press(arm.arm, { ...rejecting, now: 1_500 }), {
      kind: "decide",
      decision: "reject",
    });
  }
});
