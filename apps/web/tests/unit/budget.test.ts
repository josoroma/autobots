/**
 * Pins the budget choices the goal composer and the workflow editor share (R-37, PRD-Studio WF-05),
 * from the server's range (Decision 0022 D11), and the spend a run shows (PRD-Studio RN-03).
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import type { BudgetRange } from "@autobots/api-client";

import {
  budgetChoices,
  budgetFor,
  budgetOffer,
  FALLBACK_BUDGET_MICRO_USD,
  MAX_BUDGET_CHOICES,
  spendOf,
} from "../../lib/budget.ts";

const range = (changes: Partial<BudgetRange> = {}): BudgetRange => ({
  min_micro_usd: 250_000,
  max_micro_usd: 2_000_000,
  step_micro_usd: 250_000,
  default_micro_usd: 1_000_000,
  remaining_daily_micro_usd: 2_100_000,
  ...changes,
});

test("the choices run from the range's lowest to its highest, in its steps", () => {
  assert.deepEqual(budgetOffer(range()), {
    kind: "offered",
    choices: [
      250_000, 500_000, 750_000, 1_000_000, 1_250_000, 1_500_000, 1_750_000,
      2_000_000,
    ],
    defaultMicroUsd: 1_000_000,
  });
  // D11's whole range, US$0.25 to US$5.00, is twenty choices.
  assert.deepEqual(budgetOffer(range({ max_micro_usd: 5_000_000 })), {
    kind: "offered",
    choices: Array.from({ length: 20 }, (_, index) => (index + 1) * 250_000),
    defaultMicroUsd: 1_000_000,
  });
});

test("nothing left today offers no choice, and keeps the server's default", () => {
  assert.deepEqual(
    budgetOffer(
      range({
        max_micro_usd: 0,
        default_micro_usd: 0,
        remaining_daily_micro_usd: 100_000,
      }),
    ),
    { kind: "offered", choices: [], defaultMicroUsd: 0 },
  );
});

test("no range yet means the server's choices aren't known", () => {
  assert.deepEqual(budgetOffer(null), { kind: "unknown" });
});

test("a step of zero or less is refused rather than expanded", () => {
  assert.deepEqual(budgetOffer(range({ step_micro_usd: 0 })), {
    kind: "unknown",
  });
  assert.deepEqual(budgetOffer(range({ step_micro_usd: -250_000 })), {
    kind: "unknown",
  });
});

test("a range with more choices than the cap is refused rather than listed", () => {
  assert.equal(MAX_BUDGET_CHOICES, 100);
  const widest = range({
    min_micro_usd: 1,
    step_micro_usd: 1,
    max_micro_usd: MAX_BUDGET_CHOICES,
  });
  const offer = budgetOffer(widest);
  assert.equal(offer.kind === "offered" ? offer.choices.length : 0, 100);
  assert.deepEqual(
    budgetOffer({ ...widest, max_micro_usd: MAX_BUDGET_CHOICES + 1 }),
    { kind: "unknown" },
  );
  assert.deepEqual(
    budgetOffer(range({ step_micro_usd: 1, max_micro_usd: 5_000_000 })),
    { kind: "unknown" },
  );
});

test("the budget sent is the choice while it's offered, then the server's default", () => {
  const offer = budgetOffer(range());
  assert.equal(budgetFor(offer, 1_500_000), 1_500_000);
  assert.equal(budgetFor(offer, null), 1_000_000);
  // A choice the range no longer offers isn't sent.
  assert.equal(budgetFor(offer, 4_000_000), 1_000_000);
  assert.equal(budgetFor(offer, 1_100_000), 1_000_000);
});

test("until the range is known, the budget is D11's default of US$1.00", () => {
  assert.equal(FALLBACK_BUDGET_MICRO_USD, 1_000_000);
  assert.equal(budgetFor({ kind: "unknown" }, null), 1_000_000);
  assert.equal(budgetFor({ kind: "unknown" }, 1_500_000), 1_000_000);
});

test("the composer's chip offers the range, sends the choice and says what's left of today's cap", () => {
  const choices = budgetChoices(range(), 1_500_000);
  assert.deepEqual(choices.offer, budgetOffer(range()));
  assert.equal(choices.budget, 1_500_000);
  assert.equal(choices.exhausted, false);
  assert.equal(choices.remainingMicroUsd, 2_100_000);
  assert.equal(budgetChoices(range(), null).budget, 1_000_000);
});

test("nothing left today exhausts the chip, and what's left never reads below zero", () => {
  const spent = budgetChoices(
    range({
      max_micro_usd: 0,
      default_micro_usd: 0,
      remaining_daily_micro_usd: -50_000,
    }),
    1_000_000,
  );
  assert.equal(spent.exhausted, true);
  assert.equal(spent.budget, 0);
  assert.equal(spent.remainingMicroUsd, 0);
});

test("a range not read yet, or one that can't be expanded, isn't exhausted and sends D11's default", () => {
  assert.deepEqual(budgetChoices(null, 1_500_000), {
    offer: { kind: "unknown" },
    budget: FALLBACK_BUDGET_MICRO_USD,
    exhausted: false,
    remainingMicroUsd: null,
  });
  // A step of zero is refused rather than looped over, and today's cap still shows.
  assert.deepEqual(budgetChoices(range({ step_micro_usd: 0 }), 1_500_000), {
    offer: { kind: "unknown" },
    budget: FALLBACK_BUDGET_MICRO_USD,
    exhausted: false,
    remainingMicroUsd: 2_100_000,
  });
});

test("a run's spend counts held reservations, and is an estimate while one is held or unreported", () => {
  assert.deepEqual(spendOf(70_000, 0, false), {
    micro: 70_000,
    estimated: false,
  });
  assert.deepEqual(spendOf(70_000, 110_000, false), {
    micro: 180_000,
    estimated: true,
  });
  assert.deepEqual(spendOf(70_000, 0, true), {
    micro: 70_000,
    estimated: true,
  });
});
