/**
 * A run's profile field from a select's value (R-09). The contract types it as a ModelProfileId,
 * so it's parsed rather than sent as any string.
 */
import { parseModelProfileId, type ModelProfileId } from "@autobots/api-client";

/** Nothing for "the default", or the chosen profile. A value that isn't a profile also means the default. */
export function profileField(value: string): { run_profile?: ModelProfileId } {
  if (value === "") return {};
  try {
    return { run_profile: parseModelProfileId(value) };
  } catch {
    return {};
  }
}
