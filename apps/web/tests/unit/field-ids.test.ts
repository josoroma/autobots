/** WSYS-12: a control's description and error ids, and the aria-describedby that joins them. */
import assert from "node:assert/strict";
import { test } from "node:test";

import { describedBy, fieldIds } from "../../lib/field-ids.ts";

test("a control's parts take ids from its own", () => {
  assert.deepEqual(fieldIds("openrouter-key"), {
    description: "openrouter-key-description",
    error: "openrouter-key-error",
  });
});

test("only the parts shown describe the control, in order", () => {
  const ids = fieldIds("days");
  assert.equal(
    describedBy(ids.description, ids.error),
    "days-description days-error",
  );
  assert.equal(describedBy(false, ids.error), "days-error");
  assert.equal(describedBy(ids.description, null, undefined), ids.description);
});

test("nothing shown leaves aria-describedby off", () => {
  assert.equal(describedBy(), undefined);
  assert.equal(describedBy(false, undefined, null, ""), undefined);
});
