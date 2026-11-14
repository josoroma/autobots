/**
 * Which runs newly wait, and when the notifier polls next (PRD-Studio SE-05, WCMP-06). Pure, so
 * `node --test` covers it; `components/waiting-notifier.tsx` runs the loop in the browser.
 */
export const WAITING_TITLE: Readonly<Record<string, string>> = {
  waiting_approval: "A run waits for your approval",
  waiting_input: "A run waits for your input",
};
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
  status: string;
}

/**
 * The runs whose wait is new since the last poll, and the keys to remember. A run is keyed by its
 * status too, so one that moves from approval to input is told again. The first poll only notes.
 */
export function newlyWaiting<T extends WaitingRun>(
  seen: ReadonlySet<string> | null,
  runs: readonly T[],
): { fresh: T[]; seen: Set<string> } {
  const waiting = runs.filter((run) => WAITING_TITLE[run.status] !== undefined);
  const now = new Set(waiting.map((run) => `${run.id}:${run.status}`));
  const fresh =
    seen === null
      ? []
      : waiting.filter((run) => !seen.has(`${run.id}:${run.status}`));
  return { fresh, seen: now };
}
