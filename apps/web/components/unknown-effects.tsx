"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { csrfFetch } from "@/lib/csrf-fetch";

type Operation = { operation_id: string; tool_id: string };

const REFUSALS: Record<string, string> = {
  owner_required: "Only the workspace owner can record this.",
  operation_not_unknown: "This was already resolved.",
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

  async function record(operationId: string, outcome: string): Promise<void> {
    setMessage(null);
    const reply = await csrfFetch(
      `/api/v1/runs/${encodeURIComponent(runId)}/effects/${encodeURIComponent(operationId)}/reconcile`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: JSON.stringify({ outcome, evidence }),
      },
    ).catch(() => null);
    if (reply?.ok === true) {
      setEvidence("");
      setMessage("Recorded. Resume the run to continue.");
      onResolved();
      return;
    }
    const failure = (await reply?.json().catch(() => null)) as {
      code?: string;
    } | null;
    setMessage(REFUSALS[failure?.code ?? ""] ?? "That couldn't be recorded.");
  }

  return (
    <div data-unknown-effects="true" className="space-y-3 text-sm">
      <p>
        These may or may not have happened. Check the destination&apos;s own
        records, since no one here can tell, and an effect isn&apos;t repeated
        until you do.
      </p>
      <label htmlFor="effect-evidence" className="font-medium">
        What you saw
      </label>
      <textarea
        id="effect-evidence"
        rows={2}
        value={evidence}
        onChange={(event) => setEvidence(event.target.value)}
        className="bg-background border-input block w-full rounded-md border px-3 py-2 text-sm"
      />
      <ul className="space-y-2">
        {operations.map((operation) => (
          <li key={operation.operation_id} className="space-y-1">
            <p className="font-medium">{operation.tool_id}</p>
            <div className="flex gap-3">
              <Button
                variant="secondary"
                disabled={evidence.trim() === ""}
                onClick={() => void record(operation.operation_id, "delivered")}
              >
                It happened
              </Button>
              <Button
                variant="secondary"
                disabled={evidence.trim() === ""}
                onClick={() =>
                  void record(operation.operation_id, "not_delivered")
                }
              >
                It did not happen
              </Button>
            </div>
          </li>
        ))}
      </ul>
      {message === null ? null : <p role="status">{message}</p>}
    </div>
  );
}
