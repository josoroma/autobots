/**
 * A write sent at most once at a time, with its key held per target until an accepted reply
 * settles it (R-18, R-19, Decision 0027 D2). A press while a write is pending does nothing.
 */
import { type ErrorResponse } from "@autobots/api-client";
import { useCallback, useRef, useState } from "react";

import { readErrorResponse, readReply } from "@/lib/replies";
import {
  changesChoice,
  keeps,
  nextAttempt,
  outcomeOf,
  type Attempt,
  type Outcome,
} from "@/lib/submit";

export interface Submitted<T> {
  /** `changed`: another choice was pressed while the first one's outcome is unknown; nothing was sent. */
  outcome: Outcome | "changed";
  value: T | null;
  refusal: ErrorResponse | null;
  status: number | null;
  /** This press resent a write whose outcome was unknown. */
  retried: boolean;
  /** The write is still held, so a refusal here doesn't show the first press failed. */
  held: boolean;
  /** The held choice, for a `changed` outcome. */
  heldChoice: string | null;
}

export interface SubmitSteps<T> {
  /** The body for a new intent, or null to send nothing. Skipped while a write is held. */
  body: () => Promise<string | null> | string | null;
  send: (attempt: Attempt) => Promise<Response>;
  parse: (value: unknown) => T;
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

/** Sends one attempt and reads its reply as an outcome. */
async function sendOnce<T>(
  attempt: Attempt,
  steps: SubmitSteps<T>,
): Promise<Reply<T>> {
  const reply = await steps.send(attempt).catch(() => null);
  const value = reply?.ok === true ? await readReply(reply, steps.parse) : null;
  const refusal =
    reply !== null && !reply.ok ? await readErrorResponse(reply) : null;
  const status = reply?.status ?? null;
  return {
    outcome: outcomeOf(status, value !== null, refusal !== null),
    value,
    refusal,
    status,
  };
}

/** Another choice pressed for a held target: nothing is sent. */
function changed<T>(held: Attempt | null): Submitted<T> {
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

export function useSubmit() {
  const [pending, setPending] = useState(false);
  const busy = useRef(false);
  const unknown = useRef(new Map<string, Attempt>());
  // The held targets, as state, so a screen can show its inputs as sent while one is held.
  const [heldScopes, setHeldScopes] = useState<ReadonlySet<string>>(
    () => new Set(),
  );

  const submit = useCallback(
    async <T>(steps: SubmitSteps<T>): Promise<Submitted<T> | null> => {
      if (busy.current) return null;
      const { scope = "", choice = "", keyed = true } = steps;
      const held = keyed ? (unknown.current.get(scope) ?? null) : null;
      if (changesChoice(held, choice)) return changed<T>(held);
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
        const kept = keyed && keeps(reply.outcome, retried);
        if (kept) unknown.current.set(scope, attempt);
        // An unkeyed write holds nothing, so it never clears a keyed write's hold.
        else if (keyed) unknown.current.delete(scope);
        setHeldScopes(new Set(unknown.current.keys()));
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
