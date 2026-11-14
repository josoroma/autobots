"use client";

import { parseReconciliationResult } from "@autobots/api-client";
import { useState } from "react";

import { HeldNote } from "@/components/held-note";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/field";
import { csrfFetch } from "@/lib/csrf-fetch";
import { changedChoice, withHeld } from "@/lib/submit";
import { useSubmit } from "@/lib/use-submit";

type Operation = {
  operation_id: string;
  tool_id: string;
  generation: number;
};
type Seen = "delivered" | "not_delivered";

// Each choice in the words of its button, for a message that names it.
const CHOICES: Record<Seen, string> = {
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

export function UnknownEffects({
  runId,
  operations,
  onResolved,
}: {
  runId: string;
  operations: readonly Operation[];
  onResolved: () => void;
}) {
  const [evidence, setEvidence] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const writes = useSubmit();

  // One key per press until its outcome is known (Decision 0027 D2), so a lost reply records once.
  async function record(
    operationId: string,
    generation: number,
    outcome: Seen,
  ): Promise<void> {
    setMessage(null);
    const result = await writes.submit({
      body: () => JSON.stringify({ outcome, evidence, generation }),
      send: ({ key, body }) =>
        csrfFetch(
          `/api/v1/runs/${encodeURIComponent(runId)}/effects/${encodeURIComponent(operationId)}/reconcile`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "Idempotency-Key": key,
            },
            body,
          },
        ),
      parse: parseReconciliationResult,
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

  // The evidence is part of each held record's body, so it stays as sent (Decision 0027 D2).
  const evidenceHeld = operations.some((operation) =>
    writes.holding(operation.operation_id),
  );

  return (
    <div data-unknown-effects="true" className="space-y-3 text-sm">
      <p className="leading-relaxed">
        These may or may not have happened. Check the destination&apos;s own
        records, since no one here can tell, and an effect isn&apos;t repeated
        until you do.
      </p>
      <div className="space-y-1.5">
        <label htmlFor="effect-evidence" className="block font-medium">
          What you saw
        </label>
        <Textarea
          id="effect-evidence"
          rows={2}
          value={evidence}
          onChange={(event) => setEvidence(event.target.value)}
          readOnly={evidenceHeld}
        />
        {evidenceHeld ? <HeldNote /> : null}
      </div>
      <ul className="divide-y border-y">
        {operations.map((operation) => (
          <li
            key={operation.operation_id}
            className="flex flex-wrap items-center justify-between gap-3 py-3"
          >
            <p className="min-w-0 font-mono text-[13px] font-medium break-all">
              {operation.tool_id}
            </p>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={evidence.trim() === "" || writes.pending}
                onClick={() =>
                  void record(
                    operation.operation_id,
                    operation.generation,
                    "delivered",
                  )
                }
              >
                It happened
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={evidence.trim() === "" || writes.pending}
                onClick={() =>
                  void record(
                    operation.operation_id,
                    operation.generation,
                    "not_delivered",
                  )
                }
              >
                It did not happen
              </Button>
            </div>
          </li>
        ))}
      </ul>
      {message === null ? null : (
        <p role="status" className="text-muted-foreground">
          {message}
        </p>
      )}
    </div>
  );
}
