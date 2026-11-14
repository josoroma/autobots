/**
 * A write sent at most once at a time, with its key kept until the outcome is known (R-18, R-19,
 * Decision 0027 D2). A press while a write is pending does nothing.
 */
import { type ErrorResponse } from "@autobots/api-client";
import { useCallback, useRef, useState } from "react";

import { readErrorResponse, readReply } from "@/lib/replies";
import {
  nextAttempt,
  outcomeOf,
  resends,
  type Attempt,
  type Outcome,
} from "@/lib/submit";

export interface Submitted<T> {
  outcome: Outcome;
  value: T | null;
  refusal: ErrorResponse | null;
  status: number | null;
  /** This press resent a write whose outcome was unknown. */
  retried: boolean;
}

export interface SubmitSteps<T> {
  /** The body for a new intent, or null to send nothing. Skipped while an outcome is unknown. */
  body: () => Promise<string | null> | string | null;
  send: (attempt: Attempt) => Promise<Response>;
  parse: (value: unknown) => T;
  /** The write's target, when one hook serves several; an unknown attempt is resent only to it. */
  scope?: string;
}

export function useSubmit() {
  const [pending, setPending] = useState(false);
  const busy = useRef(false);
  const unknown = useRef<Attempt | null>(null);

  const submit = useCallback(
    async <T>(steps: SubmitSteps<T>): Promise<Submitted<T> | null> => {
      if (busy.current) return null;
      busy.current = true;
      setPending(true);
      try {
        const scope = steps.scope ?? "";
        const retried = resends(unknown.current, scope);
        const attempt = nextAttempt(
          unknown.current,
          retried ? null : await steps.body(),
          () => crypto.randomUUID(),
          scope,
        );
        if (attempt === null) return null;
        const reply = await steps.send(attempt).catch(() => null);
        const value =
          reply?.ok === true ? await readReply(reply, steps.parse) : null;
        const refusal =
          reply !== null && !reply.ok ? await readErrorResponse(reply) : null;
        const outcome = outcomeOf(
          reply?.status ?? null,
          value !== null,
          refusal !== null,
        );
        unknown.current = outcome === "unknown" ? attempt : null;
        return {
          outcome,
          value,
          refusal,
          status: reply?.status ?? null,
          retried,
        };
      } finally {
        busy.current = false;
        setPending(false);
      }
    },
    [],
  );

  return { pending, submit };
}
