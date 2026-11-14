/**
 * One write per intent (R-18, R-19, Decision 0027 D2). Once a write's outcome is unknown, its key
 * and body are held for its target until an accepted reply settles it. A retry resends them as they
 * were, so the service's idempotency answers it once, and a second paid run or charge can't come
 * from a lost reply.
 */
export type Outcome = "accepted" | "refused" | "unknown";

export interface Attempt {
  key: string;
  body: string;
  /** What the write targets, such as an approval or a command. A retry never crosses targets. */
  scope: string;
  /** What was chosen for the target, such as approve or reject. */
  choice: string;
}

/**
 * Accepted needs a 2xx whose body parsed, and refused a 4xx with the service's error envelope.
 * No reply, a 5xx, a proxy's page or a body that doesn't parse is unknown: the write may have
 * happened.
 */
export function outcomeOf(
  status: number | null,
  parsed: boolean,
  hasEnvelope: boolean,
): Outcome {
  if (status === null || status >= 500) return "unknown";
  if (status >= 200 && status < 300) return parsed ? "accepted" : "unknown";
  return hasEnvelope ? "refused" : "unknown";
}

/**
 * Whether the attempt stays held after this reply. A refusal of a resent write doesn't settle it:
 * many refusals come before the service looks at the key, such as an expired session or a budget
 * the first write already reserved, so the first press may still have gone through.
 */
export function keeps(outcome: Outcome, retried: boolean): boolean {
  return outcome === "unknown" || (retried && outcome === "refused");
}

/** The attempt to send: the held one for this target, or a new key for this body. */
export function nextAttempt(
  held: Attempt | null,
  body: string | null,
  mint: () => string,
  scope = "",
  choice = "",
): Attempt | null {
  if (held !== null) return held;
  return body === null ? null : { key: mint(), body, scope, choice };
}

/**
 * A press for another choice on a target whose write is held, such as Reject after a lost
 * Approve. Resending the held body would do what wasn't pressed, and sending the new one could
 * contradict a decision already made, so neither is sent.
 */
export function changesChoice(held: Attempt | null, choice = ""): boolean {
  return held !== null && held.choice !== choice;
}

/** Said with a refusal of a resent write, which doesn't show the first press failed. */
export const HELD_NOTE =
  "Your first press may still have gone through, so pressing again resends it rather than doing it twice.";

/** A refusal's text, with the held note when it answered a resent write. */
export function withHeld(text: string, held: boolean): string {
  return held ? `${text} ${HELD_NOTE}` : text;
}

/**
 * Said beside a held write's inputs, which stay as they were sent: a changed body after a lost reply
 * can't be told from a correction made in the belief nothing started (Decision 0027 D2).
 */
export const HELD_INPUTS =
  "These stay as sent, since the first request may already have gone through. A reload shows what happened.";

/** Said for a `changed` press: nothing was sent, and the held choice may already be recorded. */
export function changedChoice(held: string): string {
  return `Nothing was sent. Your first choice, "${held}", may already be recorded, as its reply was lost. Reload to see it before choosing differently.`;
}

/**
 * A reply's words when it wasn't accepted: the screen's own for a refusal's code, else the
 * service's message, or `lost` when no refusal came back (R-19 step 4).
 */
export function refusalText(
  table: Readonly<Record<string, string>>,
  refusal: { code: string; message: string } | null,
  lost: string,
): string {
  if (refusal === null) return lost;
  return table[refusal.code] ?? refusal.message;
}
