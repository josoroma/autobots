/**
 * Starting a session with Experts and opening it (US-5.1): direct with one, or a coordinator among
 * several. Nothing runs until Run is pressed in the session. One write at a time per screen, and one
 * key per target until its outcome is known (Decision 0027 D2). The Experts list and the Expert
 * editor share it.
 */
import { parseSessionView, type SessionCreate } from "@autobots/api-client";
import { useRouter } from "next/navigation";
import { useCallback } from "react";

import { csrfFetch } from "@/lib/csrf-fetch";
import { sessionBody, sessionText } from "@/lib/studio-writes";
import { useSubmit } from "@/lib/use-submit";

export interface StartSession {
  /** Opens the session, or returns why it didn't open; null when nothing is to be said. */
  start: (
    kind: SessionCreate["kind"],
    expertIds: readonly string[],
    scope?: string,
  ) => Promise<string | null>;
  pending: boolean;
  /** Whether a start for this target is held, so what it names stays as sent. */
  holding: (scope?: string) => boolean;
}

export function useStartSession(): StartSession {
  const { submit, pending, holding } = useSubmit();
  const router = useRouter();

  const start = useCallback(
    async (
      kind: SessionCreate["kind"],
      expertIds: readonly string[],
      scope = "",
    ): Promise<string | null> => {
      const result = await submit({
        body: () => JSON.stringify(sessionBody(kind, expertIds)),
        send: ({ key, body }) =>
          csrfFetch("/api/v1/sessions", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "Idempotency-Key": key,
            },
            body,
          }),
        parse: parseSessionView,
        scope,
      });
      if (result === null) return null;
      if (result.outcome === "accepted" && result.value !== null) {
        router.push(`/sessions/${result.value.id}`);
        return null;
      }
      return sessionText(result);
    },
    [submit, router],
  );

  return { start, pending, holding };
}
