/**
 * What the run page derives from a run's stored events (R-49, WRUN-01, WRUN-15): the timeline's
 * words, merging replays by sequence, live result text, the newest published result and the count
 * of tool-use events. Pure and JSX-free; `connection.ts` and the run page's hooks use it.
 */
import type { RunEvent } from "@autobots/api-client";

/**
 * A timeline line for each payload type. A type the contract gains fails the type check here until
 * it has words (XTYP-06).
 */
export function describeEvent(event: RunEvent): string {
  const payload = event.payload;
  switch (payload.type) {
    case "run.status_changed":
      return payload.previous === payload.current
        ? `Run ${payload.current}`
        : `Run moved from ${payload.previous} to ${payload.current}`;
    case "effect.reconciled":
      return `An unknown effect was reconciled: ${payload.outcome.replaceAll("_", " ")}`;
    case "approval.requested":
      return `Approval requested for ${payload.tool_id}`;
    case "approval.decided":
      return `Approval ${payload.decision}`;
    case "tool.use.started":
      return `Tool ${payload.tool_id} started`;
    case "tool.use.completed":
      return `Tool ${payload.tool_id} ${payload.outcome}${payload.code ? ` (${payload.code})` : ""}`;
    case "result.text.delta":
      return "Result text";
    case "artifact.published":
      return `Artifact ${payload.name} published`;
    case "artifact.missing":
      return `Artifact ${payload.name} is missing`;
  }
}

/**
 * Stored events by sequence, so a replayed one replaces itself rather than repeating (SP-011).
 * Nothing to add keeps the same map, so what is derived from it isn't derived again.
 */
export function mergeEvents(
  current: ReadonlyMap<number, RunEvent>,
  incoming: readonly RunEvent[],
): ReadonlyMap<number, RunEvent> {
  if (incoming.length === 0) return current;
  const events = new Map(current);
  for (const event of incoming) events.set(event.sequence, event);
  return events;
}

/** Stored events oldest first, as the timeline lists them. */
export function toTimeline(events: Iterable<RunEvent>): RunEvent[] {
  return [...events].sort((a, b) => a.sequence - b.sequence);
}

/** The newest published artifact, which the page shows as the run's stored result. */
export function latestPublished(
  events: Iterable<RunEvent>,
): { id: string; name: string } | null {
  let newest: { sequence: number; id: string; name: string } | null = null;
  for (const { sequence, payload } of events) {
    if (payload.type !== "artifact.published") continue;
    if (newest !== null && newest.sequence > sequence) continue;
    newest = { sequence, id: payload.artifact_id, name: payload.name };
  }
  return newest === null ? null : { id: newest.id, name: newest.name };
}

/** How many tool-use events arrived. It changes exactly when the run's tool uses may have. */
export function toolEventCount(events: Iterable<RunEvent>): number {
  let count = 0;
  for (const event of events) {
    if (event.payload.type.startsWith("tool.use.")) count += 1;
  }
  return count;
}

/** Result text while it's written (US-15.24). Never stored, so never part of the timeline. */
export interface LiveText {
  segment: number;
  text: string;
  joined: boolean;
}

/**
 * A live piece extends the text only where it continues it. One that starts later, after a
 * reconnect, is shown as joined partway, and the stored artifact replaces it all once published.
 */
export function withDelta(
  current: LiveText | null,
  delta: { segment: number; offset: number; text: string },
): LiveText {
  if (current === null || current.segment !== delta.segment)
    return {
      segment: delta.segment,
      text: delta.text,
      joined: delta.offset > 0,
    };
  if (delta.offset + delta.text.length <= current.text.length) return current;
  if (delta.offset === current.text.length)
    return { ...current, text: current.text + delta.text };
  return { ...current, text: current.text + delta.text, joined: true };
}
