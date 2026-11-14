/**
 * A run's stream frames and replay pages, read through the generated parsers (R-09, WRUN-06). A
 * cursor frame without a number once became NaN, so every reconnect asked for after=NaN.
 */
import {
  parseEventPage,
  parseRunEvent,
  type EventPage,
  type RunEvent,
} from "@autobots/api-client";

/** Decision 0017 Q13: an event of a type this page doesn't know is skipped, never an error. */
export function knownEvent(raw: unknown): RunEvent | null {
  try {
    return parseRunEvent(raw);
  } catch {
    return null;
  }
}

function frameJson(data: unknown): unknown {
  if (typeof data !== "string") return undefined;
  try {
    return JSON.parse(data);
  } catch {
    return undefined;
  }
}

/** A `run` or `live` frame's event, or null when it is malformed or of an unknown type. */
export function parseEventFrame(data: unknown): RunEvent | null {
  return knownEvent(frameJson(data));
}

/** A `cursor` frame's position: a safe, non-negative integer, or null. */
export function parseCursorFrame(data: unknown): number | null {
  const value = frameJson(data);
  if (typeof value !== "object" || value === null || !("cursor" in value)) {
    return null;
  }
  const { cursor } = value;
  return typeof cursor === "number" &&
    Number.isSafeInteger(cursor) &&
    cursor >= 0
    ? cursor
    : null;
}

export interface SplitPage {
  page: EventPage;
  events: RunEvent[];
  skipped: number;
}

/**
 * A replay page: its cursor and gap as the contract states them, its known events, and how many
 * it skipped. Throws the parser's ContractError when the page itself has drifted.
 */
export function splitEventPage(raw: unknown): SplitPage {
  const record: Record<string, unknown> =
    typeof raw === "object" && raw !== null && !Array.isArray(raw)
      ? { ...raw }
      : {};
  const listed: unknown[] = Array.isArray(record.events) ? record.events : [];
  const page = parseEventPage({ ...record, events: [] });
  const events = listed
    .map(knownEvent)
    .filter((event): event is RunEvent => event !== null);
  return { page, events, skipped: listed.length - events.length };
}
