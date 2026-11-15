/**
 * Settings → Models' provider words (PRD-Model-Providers, WSYS-07): the connection bar's source,
 * authentication and catalog, each route's qualification, and what a key action says. Tables are
 * keyed by the contract's unions, so a status it gains fails the type check here. Pure and
 * JSX-free, so `node --test` covers it.
 */
import type { ProviderStatus, RouteQualification } from "@autobots/api-client";

import { refusalText } from "./submit.ts";

export const SOURCE_LABEL: Readonly<Record<ProviderStatus["source"], string>> =
  {
    none: "None",
    app: "Stored for this workspace, encrypted on this Mac",
    environment: "The server environment, which is managed outside the app",
  };

export const AUTH_LABEL: Readonly<
  Record<ProviderStatus["auth_status"], string>
> = {
  missing:
    "No key is configured. Local work is available, and model-backed work is blocked.",
  configured: "The key authenticated.",
  invalid: "The key was rejected. Model-backed work is blocked.",
  unavailable:
    "Authentication or credential storage could not be reached. Model-backed work is blocked.",
};

export const CATALOG_LABEL: Readonly<
  Record<ProviderStatus["catalog_status"], string>
> = {
  available: "Available",
  unavailable:
    "Unavailable. New model calls stay blocked until fresh metadata exists.",
  unknown: "Not checked",
};

/** A status dot's tone. The words carry the meaning; the dot only repeats it. */
export type Tone = "ok" | "bad" | "idle";

export const AUTH_TONE: Readonly<Record<ProviderStatus["auth_status"], Tone>> =
  {
    missing: "idle",
    configured: "ok",
    invalid: "bad",
    unavailable: "bad",
  };

export const CATALOG_TONE: Readonly<
  Record<ProviderStatus["catalog_status"], Tone>
> = {
  available: "ok",
  unavailable: "bad",
  unknown: "idle",
};

export const QUALIFICATION_LABEL: Readonly<
  Record<RouteQualification["status"], string>
> = {
  qualified_with_limits: "Qualified, with the limits below",
  not_qualified: "Not qualified",
};

export const QUALIFICATION_TONE: Readonly<
  Record<RouteQualification["status"], "success" | "muted">
> = {
  qualified_with_limits: "success",
  not_qualified: "muted",
};

/** R-19: each action says what it did, so Validate and Disconnect never report "Saved.". */
export const KEY_SAVED = "Saved.";
export const KEY_VALIDATED = "Checked. The key's status above is current.";
export const KEY_DISCONNECTED = "Disconnected. The saved key is removed.";

// R-19 step 4: this screen's words for a refusal's code. Any other keeps the service's own, which
// are fixed per code and never echo a key.
const REFUSALS: Readonly<Record<string, string>> = {
  not_signed_in:
    "Your session ended. Sign in, then try again. Nothing changed.",
  owner_required: "Only the workspace owner can change the OpenRouter key.",
};
const LOST =
  "The reply was lost, so this may have applied. The status above is reloaded.";

/** What a key action says: `done` once accepted, else why in this screen's words. */
export function keyActionText(
  accepted: boolean,
  refusal: { code: string; message: string } | null,
  done: string,
): string {
  return accepted ? done : refusalText(REFUSALS, refusal, LOST);
}
