/**
 * Settings → Models' policy rules (PRD-Studio MD-01 to MD-03, WSYS-06): the draft and what counts
 * as a change, which profiles each select offers, whether a saved choice is no longer offered, how
 * many roles follow the workspace default, and the bodies and words of a save and a reset. The
 * panel describes only the saved policy, so it can't say a draft has taken effect. Pure and
 * JSX-free, so `node --test` covers it.
 */
import type {
  BindingSource,
  ExpectedVersion,
  ModelAvailability,
  ModelPolicyState,
  ModelPolicyUpdate,
  ModelProfileId,
  RoleBinding,
} from "@autobots/api-client";

import { formatUsd } from "./format.ts";
import { BINDING_SOURCE_LABEL } from "./model-roles.ts";

/** A role select's "Workspace default": the role has no override. */
export const WORKSPACE_DEFAULT = "";
/** The workspace default select's "none": each role takes its built-in default (MD-02). */
export const BUILTIN_DEFAULT = "";

/**
 * On Local one offered local profile answers every role (Decision 0041 A8): the workspace default
 * names it, so there's no built-in default to fall back on and no role override to save.
 */
export const CHOOSE_LOCAL = "Choose a local model";
export const LOCAL_ROLES =
  "On Local, the workspace default answers every role, so there are no role overrides.";

/** The form's choices, a UI model apart from the contract's ModelPolicyUpdate. */
export interface PolicyDraft {
  defaultProfile: ModelProfileId | typeof BUILTIN_DEFAULT;
  overrides: Record<string, ModelProfileId>;
}

export function draftOf(state: ModelPolicyState): PolicyDraft {
  return {
    defaultProfile: state.default_profile ?? BUILTIN_DEFAULT,
    overrides: state.role_overrides,
  };
}

/** Whether the draft chooses what's saved. */
export function sameForm(state: ModelPolicyState, draft: PolicyDraft): boolean {
  const saved: Record<string, string> = state.role_overrides;
  const roles = new Set([
    ...Object.keys(saved),
    ...Object.keys(draft.overrides),
  ]);
  return (
    (state.default_profile ?? BUILTIN_DEFAULT) === draft.defaultProfile &&
    [...roles].every((role) => saved[role] === draft.overrides[role])
  );
}

/** The overrides with one role's choice, where Workspace default removes its override. */
export function withOverride(
  overrides: Readonly<Record<string, ModelProfileId>>,
  role: string,
  profile: ModelProfileId | typeof WORKSPACE_DEFAULT,
): Record<string, ModelProfileId> {
  const next = { ...overrides };
  if (profile === WORKSPACE_DEFAULT) delete next[role];
  else next[role] = profile;
  return next;
}

/**
 * The profiles a select lists: the offered ones, and its current choice even when it isn't
 * offered, shown unselectable, so the page never shows another in its place.
 */
export function choices(
  models: readonly ModelAvailability[],
  current: string | undefined,
): ModelAvailability[] {
  return models.filter((item) => item.offered || item.profile === current);
}

/** A saved default or override names a profile that isn't offered, so new runs are refused. */
export function savedChoiceNotOffered(
  state: ModelPolicyState,
  models: readonly ModelAvailability[],
): boolean {
  const notOffered = new Set<string>(
    models.filter((item) => !item.offered).map((item) => item.profile),
  );
  return (
    (state.default_profile !== null && notOffered.has(state.default_profile)) ||
    Object.values(state.role_overrides).some((profile) =>
      notOffered.has(profile),
    )
  );
}

/** How many roles follow the workspace default, or the built-in one when none is set. */
export function followingCount(bindings: readonly RoleBinding[]): number {
  return bindings.filter(
    (binding) =>
      binding.source === "workspace_default" ||
      binding.source === "builtin_default",
  ).length;
}

/** PRD-Studio MD-02: which step chose a saved role's binding. */
export function sourceText(source: BindingSource | undefined): string {
  return source === undefined ? "Not recorded" : BINDING_SOURCE_LABEL[source];
}

/** Micro-USD per 1M tokens, in the app's one money format. */
export function perMillion(micro: number | null): string {
  return micro === null ? "not listed" : formatUsd(micro);
}

export function fetchedAt(value: string | null): string {
  if (value === null) return "The catalog couldn't be fetched.";
  const when = new Date(value);
  return `Catalog fetched ${when.toLocaleString("en-US", {
    dateStyle: "medium",
    timeStyle: "medium",
  })}.`;
}

export function modelLabel(canonicalId: string, wireId: string): string {
  return `${canonicalId} (requested as ${wireId})`;
}

/** The save's body, under the version this screen loaded. */
export function policyBody(
  state: ModelPolicyState,
  draft: PolicyDraft,
): ModelPolicyUpdate {
  return {
    expected_version: state.version,
    default_profile:
      draft.defaultProfile === BUILTIN_DEFAULT ? null : draft.defaultProfile,
    role_overrides: draft.overrides,
  };
}

/** MD-03: Reset all clears every role override under the version this screen loaded. */
export function resetBody(state: ModelPolicyState): ExpectedVersion {
  return { expected_version: state.version };
}

export const POLICY_SAVED =
  "Saved. New runs freeze this, and admitted runs keep theirs.";
export const POLICY_RESET =
  "Every role override is cleared. New runs freeze this, and admitted runs keep theirs.";
export const POLICY_DISCARDED = "Discarded. The form shows the saved policy.";

// R-19 step 4: this screen's words for a refusal's code, per action. Any other keeps the service's.
export const SAVE_REFUSALS: Readonly<Record<string, string>> = {
  stale_version:
    "This policy changed after you opened it, so nothing was saved. Reload the page and try again.",
};
export const RESET_REFUSALS: Readonly<Record<string, string>> = {
  stale_version:
    "This policy changed after you opened it, so nothing was reset. Reload the page and try again.",
};
export const POLICY_LOST =
  "The reply was lost, so this may have applied. Reload the page to see the policy now.";
