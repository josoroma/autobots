import assert from "node:assert/strict";
import { test } from "node:test";

import { schemaValue } from "../../lib/schema-value.ts";

test("behind, equal and ahead read the applied count against the shipped one", () => {
  assert.equal(schemaValue(35, 49), "35 of 49 migrations applied.");
  assert.equal(schemaValue(49, 49), "49 of 49 migrations applied.");
  assert.equal(schemaValue(50, 49), "50 of 49 migrations applied.");
});

test("without a readable history it says so, with the shipped count", () => {
  assert.equal(
    schemaValue(null, 1049),
    "1,049 migrations in this version, and no readable history.",
  );
});
