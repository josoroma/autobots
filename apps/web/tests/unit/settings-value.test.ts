/**
 * Pins which value a settings panel shows (WSYS-03): a write's reply is never hidden by a read that
 * settled before the reply arrived, and a read that settles after it shows. The case behind it: a
 * refused Validate starts a reload, Disconnect is pressed, the reload settles, then the DELETE is
 * accepted, and the panel must show the disconnected status.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import { shownValue } from "../../lib/settings-value.ts";

test("with no write, the read shows", () => {
  assert.equal(shownValue("read", 100, null), "read");
  assert.equal(shownValue(null, null, null), null);
});

test("a read that settled before the reply arrived doesn't hide it", () => {
  assert.equal(
    shownValue("app key", 200, { at: 300, value: "disconnected" }),
    "disconnected",
  );
  assert.equal(
    shownValue(null, null, { at: 300, value: "disconnected" }),
    "disconnected",
  );
});

test("a read that settles after the reply shows", () => {
  assert.equal(
    shownValue("reloaded", 400, { at: 300, value: "replied" }),
    "reloaded",
  );
});

test("within the same millisecond the reply is kept", () => {
  assert.equal(
    shownValue("read", 300, { at: 300, value: "replied" }),
    "replied",
  );
});
