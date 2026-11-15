/**
 * How a tool use reads (PRD-Tool-Catalog TV-01 to TV-03): when, its public inputs and result in
 * brief, and its outcome in words. Only public fields, digests and sizes reach these texts; content
 * never does. Pure and JSX-free; the run page's Tools used and the workflow monitor show them.
 */
import type { ToolUseView } from "@autobots/api-client";

const OUTCOMES: Readonly<Record<NonNullable<ToolUseView["outcome"]>, string>> =
  {
    succeeded: "Succeeded",
    failed: "Failed",
    unknown: "Outcome unknown",
    denied: "Denied",
  };

/** The request's local time, then how long it took once known. */
export function toolUseWhen(use: ToolUseView): string {
  const time = new Date(use.requested_at).toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  return use.duration_ms === null ? time : `${time}, ${use.duration_ms} ms`;
}

/** Public values as `key: value` pairs, each cut to 80 characters. */
export function brief(values: Record<string, unknown> | null): string {
  if (values === null || Object.keys(values).length === 0) return "";
  return Object.entries(values)
    .map(([key, value]) => {
      const text = typeof value === "string" ? value : JSON.stringify(value);
      return `${key}: ${text.length > 80 ? `${text.slice(0, 79)}…` : text}`;
    })
    .join("; ");
}

export function toolResult(use: ToolUseView): string {
  const shown = brief(use.output_public);
  if (shown !== "") return shown;
  if (use.output_bytes !== null) return `${use.output_bytes} bytes, not shown`;
  return "Nothing returned";
}

export function toolOutcome(use: ToolUseView): string {
  if (use.outcome === null) return "Not finished";
  const text = OUTCOMES[use.outcome];
  return use.code === null ? text : `${text}: ${use.code.replaceAll("_", " ")}`;
}
