"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/field";
import { csrfFetch } from "@/lib/csrf-fetch";

type Operation = {
  operation_id: string;
  tool_id: string;
  generation: number;
};

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

  async function record(
    operationId: string,
    generation: number,
    outcome: string,
  ): Promise<void> {
    setMessage(null);
    const reply = await csrfFetch(
      `/api/v1/runs/${encodeURIComponent(runId)}/effects/${encodeURIComponent(operationId)}/reconcile`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: JSON.stringify({ outcome, evidence, generation }),
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
        />
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
                disabled={evidence.trim() === ""}
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
                disabled={evidence.trim() === ""}
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
