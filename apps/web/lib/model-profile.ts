/**
 * A run's profile field from a select's value (R-09), and each profile's short name (R-37). The
 * contract types the field as a ModelProfileId, so it's parsed rather than sent as any string.
 */
import { parseModelProfileId, type ModelProfileId } from "@autobots/api-client";

/**
 * Nothing for "the default", or the chosen profile. A value that isn't a profile is null, so the
 * screen refuses it and sends nothing: it never becomes the default, as there's no hidden model
 * default or fallback (PRD-Model-Providers MP-A08).
 */
export function profileField(
  value: string,
): { run_profile?: ModelProfileId } | null {
  if (value === "") return {};
  try {
    return { run_profile: parseModelProfileId(value) };
  } catch {
    return null;
  }
}

/**
 * A select's choice of profile: "" for none, the profile chosen, or null for a value that isn't a
 * profile, which a form then ignores, so it never becomes a default (PRD-Model-Providers MP-A08).
 */
export function profileChoice(value: string): ModelProfileId | "" | null {
  if (value === "") return "";
  return profileField(value)?.run_profile ?? null;
}

/**
 * One short name per approved profile, for every screen that names one (XDUP-10, R-37). /api/models
 * carries no display name, only canonical_id, so the web keeps this one table, keyed by the
 * generated union so that a profile the contract gains fails the type check until it has a name.
 * Which profiles new runs may use comes from ModelAvailability.offered, never from here.
 */
export const PROFILE_NAME: Readonly<Record<ModelProfileId, string>> = {
  openrouter_terra: "Terra",
  openrouter_sol: "Sol",
  openrouter_deepseek_flash: "DeepSeek Flash",
};

function isProfile(value: string): value is ModelProfileId {
  return Object.hasOwn(PROFILE_NAME, value);
}

/** The name for a profile a contract field types as a string, or the value as sent. */
export function profileName(profile: string): string {
  return isProfile(profile) ? PROFILE_NAME[profile] : profile;
}
