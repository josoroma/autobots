/**
 * Which runs newly wait, and when the notifier polls next (PRD-Studio SE-05, WCMP-06). Pure, so
 * `node --test` covers it; `components/waiting-notifier.tsx` runs the loop in the browser.
 */
import type { RunStatus } from "@autobots/api-client";

// The statuses that wait for a person, keyed by the generated RunStatus (WCMP-14).
export const WAITING_TITLE = {
  waiting_approval: "A run waits for your approval",
  waiting_input: "A run waits for your input",
} as const satisfies Partial<Record<RunStatus, string>>;

export type WaitingStatus = keyof typeof WAITING_TITLE;

export function isWaiting(status: RunStatus): status is WaitingStatus {
  return Object.hasOwn(WAITING_TITLE, status);
}
export const EVERY_MS = 4_000;
// Signed out or not a member: sign-in navigates without a page load, so the notifier keeps asking.
export const SIGNED_OUT_MS = 60_000;
export const MAX_MS = 60_000;

export type PollResult = "runs" | "signed_out" | "failed";

/** Every outcome schedules another poll. Failures back off from 8 s, doubling, up to a minute. */
export function pollDelay(result: PollResult, failures: number): number {
  if (result === "runs") return EVERY_MS;
  if (result === "signed_out") return SIGNED_OUT_MS;
  return Math.min(EVERY_MS * 2 ** failures, MAX_MS);
}

interface WaitingRun {
  id: string;
  status: RunStatus;
}

/**
 * The runs whose wait is new since the last poll, and the keys to remember. A run is keyed by its
 * status too, so one that moves from approval to input is told again. The first poll only notes.
 */
export function newlyWaiting<T extends WaitingRun>(
  seen: ReadonlySet<string> | null,
  runs: readonly T[],
): { fresh: T[]; seen: Set<string> } {
  const waiting = runs.filter((run) => isWaiting(run.status));
  const now = new Set(waiting.map((run) => `${run.id}:${run.status}`));
  const fresh =
    seen === null
      ? []
      : waiting.filter((run) => !seen.has(`${run.id}:${run.status}`));
  return { fresh, seen: now };
}
