/**
 * What a person reads after pressing Run (R-18). One table for the composer, sessions and
 * Continue, so the screens can't drift apart.
 */
import { type ErrorResponse } from "@autobots/api-client";

/** The outcome is unknown, so pressing again resends the same request and starts nothing new. */
export const ADMISSION_UNKNOWN =
  "The reply was lost, so the run may have started. Pressing Run again won't start a second one.";

const REFUSALS: Readonly<Record<string, string>> = {
  credentials_required: "Model-backed work needs an OpenRouter key.",
  model_not_offered:
    "A saved model choice isn't offered for new runs until it's qualified, so no run started. Your goal is kept.",
};

export function admissionRefusal(
  refusal: ErrorResponse | null,
  status: number | null,
): string {
  const known = REFUSALS[refusal?.code ?? ""];
  if (known !== undefined) return known;
  if (refusal?.code.startsWith("budget_") === true) return refusal.message;
  if (status === 422) {
    return "That request isn't approved, so no run started. Your goal is kept.";
  }
  return refusal?.message ?? "That could not be started.";
}
