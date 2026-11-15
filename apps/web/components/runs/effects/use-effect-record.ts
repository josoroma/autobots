import { reconcileRunEffect, type EffectEvidence } from "@autobots/api-client";
import { useState } from "react";

import { writes as writeClient } from "@/lib/api/browser";
import { changedChoice, withHeld } from "@/lib/submit";
import { useSubmit } from "@/lib/use-submit";

export type Seen = EffectEvidence["outcome"];

// Each choice in the words of its button, for a message that names it.
export const CHOICES: Readonly<Record<Seen, string>> = {
  delivered: "It happened",
  not_delivered: "It did not happen",
};

function choiceLabel(choice: string | null): string {
  return choice === "delivered" || choice === "not_delivered"
    ? CHOICES[choice]
    : (choice ?? "");
}

const REFUSALS: Record<string, string> = {
  owner_required: "Only the workspace owner can record this.",
  operation_not_unknown: "This was already resolved.",
  operation_attempt_changed:
    "This operation has been tried again since this page loaded. Reload, then check the destination again.",
};

/** An owner's report of what a destination's own records show, for an effect of unknown outcome. */
export function useEffectRecord(runId: string, onResolved: () => void) {
  const [evidence, setEvidence] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const writes = useSubmit<EffectEvidence>();

  // One key per press until its outcome is known (Decision 0027 D2), so a lost reply records once.
  async function record(
    operationId: string,
    generation: number,
    outcome: Seen,
  ): Promise<void> {
    setMessage(null);
    const result = await writes.submit({
      body: () => ({ outcome, evidence, generation }),
      send: ({ key, body }) =>
        reconcileRunEffect(writeClient, runId, operationId, body, {
          "Idempotency-Key": key,
        }),
      scope: operationId,
      // A press for the other answer while this one is held sends nothing (Decision 0027 D2).
      choice: outcome,
    });
    if (result === null) return;
    if (result.outcome === "changed") {
      setMessage(changedChoice(choiceLabel(result.heldChoice)));
      return;
    }
    if (result.outcome === "accepted") {
      setEvidence("");
      setMessage("Recorded. Resume the run to continue.");
      onResolved();
      return;
    }
    setMessage(
      result.outcome === "unknown"
        ? "This may have been recorded. The reply was lost, so pressing again won't record it twice."
        : withHeld(
            REFUSALS[result.refusal?.code ?? ""] ??
              "That couldn't be recorded.",
            result.held,
          ),
    );
  }

  return {
    evidence,
    setEvidence,
    message,
    pending: writes.pending,
    holding: writes.holding,
    record,
  };
}
