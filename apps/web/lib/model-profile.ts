/**
 * A run's profile field from a select's value (R-09). The contract types it as a ModelProfileId,
 * so it's parsed rather than sent as any string.
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
