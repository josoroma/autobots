/**
 * Each local service's state in words and tone, for the shell's health line (PRD-Studio SH-04) and
 * Home's chips (HM-05), from one table (WSHL-19). It's keyed by the contract's states, so a state
 * the contract gains fails the type check until it's described. The words carry the meaning; the
 * tone only repeats them (DS-03). Pure and JSX-free, so `node --test` covers it.
 */
import type { MemberReadiness } from "@autobots/api-client";

export type Service = MemberReadiness["services"][number];
export type Tone = "success" | "attention" | "muted";

export const SERVICE_LABEL: Readonly<Record<Service["name"], string>> = {
  api: "Python API",
  worker: "Worker",
  database: "Database",
  openrouter: "OpenRouter",
  local_model: "Local model",
};

// Decision 0041 A13: on Local, Home's model service is the owner's llama-server, read from its
// health check by code, as the API reports it.
const LOCAL_MODEL_WORDS: Readonly<Record<string, string>> = {
  local_ready: "ready",
  local_not_running: "isn't running",
  local_other_model: "is serving another model",
  local_not_offered: "isn't offered yet",
};

export const READINESS: Readonly<
  Record<
    Service["state"],
    { words: string; openrouterWords: string; tone: Tone }
  >
> = {
  ready: { words: "ready", openrouterWords: "authenticated", tone: "success" },
  not_ready: {
    words: "not ready",
    openrouterWords: "not authenticated",
    tone: "attention",
  },
  unknown: { words: "unknown", openrouterWords: "unknown", tone: "muted" },
};

export function stateWords(service: Service): string {
  const entry = READINESS[service.state];
  if (service.name === "local_model") {
    return LOCAL_MODEL_WORDS[service.code] ?? entry.words;
  }
  return service.name === "openrouter" ? entry.openrouterWords : entry.words;
}

/** SH-04: the first service that isn't ready, in its own tone, or that all are ready. */
export function healthLine(readiness: MemberReadiness): {
  field: string;
  words: string;
  tone: Tone;
} {
  const first = readiness.services.find((item) => item.state !== "ready");
  if (first === undefined) {
    return {
      field: "ready",
      words: "All local services ready",
      tone: READINESS.ready.tone,
    };
  }
  return {
    field: first.name,
    words: `${SERVICE_LABEL[first.name]} ${stateWords(first)}`,
    tone: READINESS[first.state].tone,
  };
}
