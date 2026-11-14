/**
 * One write per intent (R-18, R-19, Decision 0027 D2). A key lasts until the write's outcome is
 * known. While it's unknown, a retry resends the same body under the same key, so the service's
 * idempotency answers it once, and a second paid run or charge can't come from a lost reply.
 */
export type Outcome = "accepted" | "refused" | "unknown";

export interface Attempt {
  key: string;
  body: string;
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

/** The attempt to send: the one whose outcome is unknown, or a new key for this body. */
export function nextAttempt(
  unknown: Attempt | null,
  body: string | null,
  mint: () => string,
): Attempt | null {
  if (unknown !== null) return unknown;
  return body === null ? null : { key: mint(), body };
}
