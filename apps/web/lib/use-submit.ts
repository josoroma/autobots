/**
 * A write sent at most once at a time, with its key held per target until an accepted reply
 * settles it (R-18, R-19, Decision 0027 D2). A press while a write is pending does nothing. Each
 * write is a generated operation called with the browser's write client (R-48), which parses its
 * reply; `B` is the operation's request body type.
 */
import { type ErrorResponse } from "@autobots/api-client";
import { useCallback, useRef, useState } from "react";

import { failureOf } from "@/lib/api/browser";
import {
  heldFor,
  nextAttempt,
  outcomeOf,
  settle,
  type Attempt,
  type Holds,
  type Outcome,
} from "@/lib/submit";

export interface Submitted<T> {
  /** `changed`: another choice was pressed while the first one's outcome is unknown; nothing was sent. */
  outcome: Outcome | "changed";
  value: T | null;
  refusal: ErrorResponse | null;
  /** The status of a reply that wasn't accepted, or null when none arrived or it drifted. */
  status: number | null;
  /** This press resent a write whose outcome was unknown. */
  retried: boolean;
  /** The write is still held, so a refusal here doesn't show the first press failed. */
  held: boolean;
  /** The held choice, for a `changed` outcome. */
  heldChoice: string | null;
}

export interface SubmitSteps<B, T> {
  /**
   * The body for a new intent, built anew for each, or null to send nothing. Skipped while a write
   * is held, whose body is resent as it was.
   */
  body: () => Promise<B | null> | B | null;
  /** Sends one attempt with a generated operation, which parses the reply. */
  send: (attempt: Attempt<B>) => Promise<T>;
  /** The write's target, when one hook serves several. Each target holds its own write. */
  scope?: string;
  /** What was chosen for the target, such as approve or reject. */
  choice?: string;
  /**
   * False for a write with no key that replaces state whole, such as a draft save: the latest
   * body is sent each time and nothing is held.
   */
  keyed?: boolean;
}

interface Reply<T> {
  outcome: Outcome;
  value: T | null;
  refusal: ErrorResponse | null;
  status: number | null;
}

/**
 * Sends one attempt and reads its outcome. No reply, a 5xx, a refusal without the envelope or a
 * success that drifted from its contract is unknown: the write may have happened.
 */
async function sendOnce<B, T>(
  attempt: Attempt<B>,
  steps: SubmitSteps<B, T>,
): Promise<Reply<T>> {
  try {
    const value = await steps.send(attempt);
    return { outcome: "accepted", value, refusal: null, status: null };
  } catch (error) {
    const { status, refusal } = failureOf(error);
    return {
      outcome: outcomeOf(status, false, refusal !== null),
      value: null,
      refusal,
      status,
    };
  }
}

/** Another choice pressed for a held target: nothing is sent. */
function changed<B, T>(held: Attempt<B> | null): Submitted<T> {
  return {
    outcome: "changed",
    value: null,
    refusal: null,
    status: null,
    retried: false,
    held: true,
    heldChoice: held?.choice ?? null,
  };
}

/** One hook per kind of body: `B` is the generated request type its writes send. */
export function useSubmit<B>() {
  const [pending, setPending] = useState(false);
  const busy = useRef(false);
  const holds = useRef<Holds<B>>(new Map());
  // The held targets, as state, so a screen can show its inputs as sent while one is held.
  const [heldScopes, setHeldScopes] = useState<ReadonlySet<string>>(
    () => new Set(),
  );

  const submit = useCallback(
    async <T>(steps: SubmitSteps<B, T>): Promise<Submitted<T> | null> => {
      if (busy.current) return null;
      const { scope = "", choice = "", keyed = true } = steps;
      const { changed: other, held } = heldFor(
        holds.current,
        scope,
        choice,
        keyed,
      );
      if (other) return changed<B, T>(held);
      busy.current = true;
      setPending(true);
      try {
        const retried = held !== null;
        const attempt = nextAttempt(
          held,
          retried ? null : await steps.body(),
          () => crypto.randomUUID(),
          scope,
          choice,
        );
        if (attempt === null) return null;
        const reply = await sendOnce(attempt, steps);
        holds.current = settle(
          holds.current,
          attempt,
          reply.outcome,
          retried,
          keyed,
        );
        const kept = keyed && holds.current.has(scope);
        setHeldScopes(new Set(holds.current.keys()));
        return {
          ...reply,
          retried,
          held: kept,
          heldChoice: kept ? attempt.choice : null,
        };
      } finally {
        busy.current = false;
        setPending(false);
      }
    },
    [],
  );

  /** Whether a write to this target is held, so its inputs stay as they were sent. */
  const holding = useCallback(
    (scope = "") => heldScopes.has(scope),
    [heldScopes],
  );

  return { pending, submit, holding };
}
