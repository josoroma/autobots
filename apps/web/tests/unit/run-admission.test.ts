import assert from "node:assert/strict";
import { test } from "node:test";

import { admissionRefusal } from "../../lib/run-admission.ts";

test("known refusals read the same on every screen", () => {
  assert.equal(
    admissionRefusal({ code: "credentials_required", message: "x" }, 409),
    "Model-backed work needs an OpenRouter key.",
  );
  assert.match(
    admissionRefusal({ code: "model_not_offered", message: "x" }, 409),
    /isn't offered/,
  );
});

test("a budget refusal keeps the service's own words", () => {
  assert.equal(
    admissionRefusal(
      { code: "budget_over_cap", message: "Lower it to US$1.00." },
      409,
    ),
    "Lower it to US$1.00.",
  );
});

test("an invalid request and anything else", () => {
  assert.match(admissionRefusal(null, 422), /isn't approved/);
  assert.equal(
    admissionRefusal({ code: "other", message: "Try later." }, 409),
    "Try later.",
  );
  assert.equal(admissionRefusal(null, 400), "That could not be started.");
});
