/**
 * The Model source panel's words (Decision 0041 A1, A7, A13; US-23.3): where model calls go, each
 * local profile's state, the runtime's health, the roles Local covers and what a call costs. Pure
 * and JSX-free, so `node --test` covers it.
 */
import type {
  LocalProfileState,
  LocalRuntime,
  ModelSourceState,
} from "@autobots/api-client";

export const SOURCE_CHOICES: ReadonlyArray<{
  value: ModelSourceState["source"];
  label: string;
  detail: string;
}> = [
  {
    value: "openrouter",
    label: "OpenRouter",
    detail: "Today's profiles: Terra, with Sol for browsing.",
  },
  {
    value: "local",
    label: "Local",
    detail: "Models served on this Mac. Nothing goes to OpenRouter.",
  },
];

export const SPEND_NOTE =
  "US$0.00 per model call. Token, call, tool and time limits still apply.";
export const TOOLS_NOTE =
  "Tool calls such as SerpApi, Jina and YouTube still leave the Mac.";
export const NO_MATCH = "No run matched yet";

export const SOURCE_REFUSALS: Readonly<Record<string, string>> = {
  owner_required: "Only the workspace owner can switch Model source.",
  stale_version: "The policy changed. Reload and try again.",
};

/** One local profile's line: qualified with its date, or why it isn't offered. */
export function profileLine(profile: LocalProfileState): string {
  if (profile.offered) {
    const when =
      profile.qualified_on === null ? "" : ` ${profile.qualified_on}`;
    return `Qualified${when} · llama-server · 64K context`;
  }
  return profile.reason ?? "Not offered.";
}

export function matchedLine(profile: LocalProfileState): string {
  return profile.matched_runs.length === 0
    ? NO_MATCH
    : `Matched: ${profile.matched_runs.join(", ")}`;
}

/** The runtime's health, with the model ID it serves and whether its file matches the pin. */
export function runtimeLine(runtime: LocalRuntime | null): string {
  if (runtime === null) return "No local profile is offered yet.";
  const at = `127.0.0.1:${runtime.port}`;
  if (runtime.status === "not_running") {
    return `Not running on ${at}. Start it with the runbook command.`;
  }
  if (runtime.status === "other_model") {
    const served = runtime.served_model_id ?? "another model";
    return `Serving "${served}" on ${at}, not this profile's model.`;
  }
  const digest =
    runtime.sha256_matches === true
      ? ", pinned SHA-256 matches"
      : runtime.sha256_matches === false
        ? ", but its file doesn't match the pinned SHA-256"
        : runtime.sha256_checking
          ? ", checking its file's SHA-256"
          : "";
  return `Ready: serving "${runtime.served_model_id ?? ""}" on ${at}${digest}.`;
}

/** The roles Local covers, or which ones keep it from being chosen. */
export function rolesLine(state: ModelSourceState): string {
  const names = (roles: readonly string[]) => roles.join(" and ");
  if (state.roles_uncovered.length > 0) {
    return `No offered local profile covers ${names(state.roles_uncovered)} yet, so Local can't be chosen.`;
  }
  return `${names(state.roles_needed)} use the local model, as every role does on Local.`;
}

export function sourceLabel(source: ModelSourceState["source"]): string {
  return (
    SOURCE_CHOICES.find((choice) => choice.value === source)?.label ?? source
  );
}
