import assert from "node:assert/strict";
import { test } from "node:test";

import {
  ADMISSION_FIX,
  admissionKind,
  admissionRefusal,
} from "../../lib/run-admission.ts";

test("known refusals read the same on every screen", () => {
  assert.equal(
    admissionRefusal({ code: "credentials_required", message: "x" }, 409),
    "Model-backed work needs an OpenRouter key.",
  );
  assert.match(
    admissionRefusal({ code: "model_not_offered", message: "x" }, 409),
    /isn't offered/,
  );
  assert.match(
    admissionRefusal({ code: "credential_invalid", message: "x" }, 409),
    /was rejected/,
  );
});

test("a budget refusal keeps the service's own words, and says no run started", () => {
  assert.equal(
    admissionRefusal(
      { code: "budget_over_cap", message: "Lower it to US$1.00." },
      409,
    ),
    "Lower it to US$1.00. No run started.",
  );
  // A budget out of range is a 422 too, and is still a budget refusal.
  assert.equal(
    admissionKind({ code: "budget_out_of_range", message: "x" }, 422),
    "budget_refused",
  );
});

test("an invalid request and anything else", () => {
  assert.match(admissionRefusal(null, 422), /isn't approved/);
  assert.equal(
    admissionRefusal({ code: "other", message: "Try later." }, 409),
    "Try later.",
  );
  assert.equal(admissionRefusal(null, 400), "That could not be started.");
  assert.equal(admissionKind(null, 400), "error");
});

test("only refusals settings can fix link there", () => {
  assert.equal(ADMISSION_FIX.credentials_required, "Set up OpenRouter");
  assert.equal(ADMISSION_FIX.model_not_offered, "Change it in settings");
  assert.equal(ADMISSION_FIX.budget_refused, undefined);
  assert.equal(ADMISSION_FIX.error, undefined);
});
