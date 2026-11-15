/**
 * A run's event stream in one place: the frame names the service's contract declares, the
 * browser's EventSource, and each frame's body read through the generated parsers (R-09, R-49,
 * XTYP-07). A cursor is a safe, non-negative integer or nothing, so a reconnect never asks for
 * after=NaN (WRUN-06). Runs in the browser and under `node --test`, which never opens a stream.
 */
import {
  parseEventPage,
  parseRunEvent,
  parseStreamCursor,
  schemas,
  type EventPage,
  type RunEvent,
  type StreamFrame,
} from "@autobots/api-client";

/** The stream's named frames, as the contract's StreamFrame lists them (event_routes.py). */
export const FRAME_TYPES: readonly StreamFrame[] = schemas.StreamFrame.enum;

export interface StreamHandlers {
  open(): void;
  error(): void;
  frame(type: StreamFrame, data: unknown): void;
}

export interface Stream {
  close(): void;
}

/** The browser's EventSource on `url`, passing on each named frame's body as it arrives. */
export function openEventSource(url: string, on: StreamHandlers): Stream {
  const source = new EventSource(url);
  source.onopen = () => on.open();
  source.onerror = () => on.error();
  for (const type of FRAME_TYPES) {
    source.addEventListener(type, (message) => on.frame(type, message.data));
  }
  return source;
}

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

/** A `cursor` frame's StreamCursor position: a safe, non-negative integer, or null. */
export function parseCursorFrame(data: unknown): number | null {
  try {
    return parseStreamCursor(frameJson(data)).cursor;
  } catch {
    return null;
  }
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
