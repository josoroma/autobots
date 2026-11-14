/**
 * What a person reads after pressing Run (R-18). One table for the composer, sessions and
 * Continue, so the screens can't drift apart.
 */
import { type ErrorResponse } from "@autobots/api-client";

/** The outcome is unknown, so pressing again resends the same request and starts nothing new. */
export const ADMISSION_UNKNOWN =
  "The reply was lost, so the run may have started. Pressing Run again won't start a second one.";

/** A chosen model that isn't a profile is refused on the page, so nothing is sent (PRD-Model-Providers MP-A08). */
export const CHOICE_NOT_OFFERED = "That model isn't offered. Choose another.";

/** Why a run wasn't admitted, as the screens tell it. */
export type AdmissionRefusal =
  | "credentials_required"
  | "credential_invalid"
  | "credential_unavailable"
  | "model_not_offered"
  | "budget_refused"
  | "model_refused"
  | "error";

// The service's codes each screen names in its own words.
const NAMED: readonly AdmissionRefusal[] = [
  "credentials_required",
  "credential_invalid",
  "credential_unavailable",
  "model_not_offered",
];

const REFUSALS: Readonly<Partial<Record<AdmissionRefusal, string>>> = {
  credentials_required: "Model-backed work needs an OpenRouter key.",
  credential_invalid: "The configured key was rejected.",
  credential_unavailable:
    "Credential storage is unavailable, so model-backed work is blocked.",
  model_not_offered:
    "A saved model choice isn't offered for new runs until it's qualified, so no run started.",
  model_refused: "That model or request isn't approved, so no run started.",
};

/** The settings link for a refusal there is fixed, by its words. */
export const ADMISSION_FIX: Readonly<
  Partial<Record<AdmissionRefusal, string>>
> = {
  credentials_required: "Set up OpenRouter",
  credential_invalid: "Fix it in settings",
  model_not_offered: "Change it in settings",
};

export function admissionKind(
  refusal: ErrorResponse | null,
  status: number | null,
): AdmissionRefusal {
  const code = refusal?.code ?? "";
  const named = NAMED.find((kind) => kind === code);
  if (named !== undefined) return named;
  if (code.startsWith("budget_")) return "budget_refused";
  return status === 422 ? "model_refused" : "error";
}

/** The table's words, a budget refusal in the service's own, or the service's message. */
export function admissionRefusal(
  refusal: ErrorResponse | null,
  status: number | null,
): string {
  const kind = admissionKind(refusal, status);
  if (kind === "budget_refused" && refusal !== null) {
    return `${refusal.message} No run started.`;
  }
  return REFUSALS[kind] ?? refusal?.message ?? "That could not be started.";
}
