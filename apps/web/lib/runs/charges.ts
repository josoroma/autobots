/**
 * The charge an owner enters for a model call with no settled charge, from OpenRouter's own
 * records: US dollars in, exact micro-USD out (PRD-Development-Harness DH-06). A charge is never
 * invented, so an entry that isn't one sends nothing and says why. Pure and JSX-free.
 */
import { MICRO_USD } from "../format.ts";

export type ChargeEntry = { micro: number } | { problem: string };

export function chargeEntry(text: string): ChargeEntry {
  const dollars = Number(text);
  if (text.trim() === "" || !Number.isFinite(dollars) || dollars < 0) {
    return { problem: "Enter the charge in US dollars, such as 0.0012." };
  }
  const micro = Math.round(dollars * MICRO_USD);
  if (dollars > 0 && micro === 0) {
    return {
      problem:
        "That's under a millionth of a dollar, which can't be recorded. Enter 0 if there was no charge.",
    };
  }
  return { micro };
}
