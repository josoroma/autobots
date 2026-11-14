/**
 * The budget choices the goal composer and the workflow editor offer, from the range the server
 * sends in RunPreview.budget (PRD-Studio WF-05, Decision 0022 D11), and the spend a run shows
 * (PRD-Studio RN-03). The server's require_budget stays the authority; these only present it (R-37).
 * Pure and JSX-free.
 */
import type { BudgetRange } from "@autobots/api-client";

/**
 * D11's default, US$1.00, shown and sent only while the server's range isn't known. Once
 * RunPreview.budget is read, its default_micro_usd is used instead.
 */
export const FALLBACK_BUDGET_MICRO_USD = 1_000_000;

/** D11's range is twenty choices. A range that would list more isn't one to offer. */
export const MAX_BUDGET_CHOICES = 100;

/**
 * `unknown` while no range is read, or when one can't be expanded: a step of zero or less, or more
 * than MAX_BUDGET_CHOICES choices. `offered` lists the choices lowest first, none when nothing is
 * left today, with the server's default.
 */
export type BudgetOffer =
  | { kind: "unknown" }
  | { kind: "offered"; choices: readonly number[]; defaultMicroUsd: number };

export function budgetOffer(range: BudgetRange | null): BudgetOffer {
  if (range === null || range.step_micro_usd <= 0) return { kind: "unknown" };
  const span = range.max_micro_usd - range.min_micro_usd;
  const count = span < 0 ? 0 : Math.floor(span / range.step_micro_usd) + 1;
  if (count > MAX_BUDGET_CHOICES) return { kind: "unknown" };
  return {
    kind: "offered",
    choices: Array.from(
      { length: count },
      (_, index) => range.min_micro_usd + index * range.step_micro_usd,
    ),
    defaultMicroUsd: range.default_micro_usd,
  };
}

/** The budget a run sends: the person's choice while it's offered, else the server's default. */
export function budgetFor(offer: BudgetOffer, chosen: number | null): number {
  if (offer.kind === "unknown") return FALLBACK_BUDGET_MICRO_USD;
  return chosen !== null && offer.choices.includes(chosen)
    ? chosen
    : offer.defaultMicroUsd;
}

/**
 * What a run has spent, counting what its reservations hold, and whether that is an estimate: it is
 * while a reservation is held or a charge went unreported (RN-03).
 */
export function spendOf(
  chargedMicroUsd: number,
  reservedMicroUsd: number,
  unreported: boolean,
): { micro: number; estimated: boolean } {
  return {
    micro: chargedMicroUsd + reservedMicroUsd,
    estimated: reservedMicroUsd > 0 || unreported,
  };
}
