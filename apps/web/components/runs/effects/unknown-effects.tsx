"use client";

import type { RunWorkspace } from "@autobots/api-client";

import { HeldNote } from "@/components/held-note";
import {
  CHOICES,
  useEffectRecord,
  type Seen,
} from "@/components/runs/effects/use-effect-record";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/field";

type Operation = Pick<
  RunWorkspace["unknown_operations"][number],
  "operation_id" | "tool_id" | "generation"
>;

const SEEN: readonly Seen[] = ["delivered", "not_delivered"];

export function UnknownEffects({
  runId,
  operations,
  onResolved,
}: {
  runId: string;
  operations: readonly Operation[];
  onResolved: () => void;
}) {
  const effects = useEffectRecord(runId, onResolved);
  // The evidence is part of each held record's body, so it stays as sent (Decision 0027 D2).
  const evidenceHeld = operations.some((operation) =>
    effects.holding(operation.operation_id),
  );
  const disabled = effects.evidence.trim() === "" || effects.pending;
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
          value={effects.evidence}
          onChange={(event) => effects.setEvidence(event.target.value)}
          readOnly={evidenceHeld}
        />
        {evidenceHeld ? <HeldNote /> : null}
      </div>
      <ul className="divide-y border-y">
        {operations.map((operation) => (
          <EffectRow
            key={operation.operation_id}
            operation={operation}
            disabled={disabled}
            onRecord={(seen) =>
              void effects.record(
                operation.operation_id,
                operation.generation,
                seen,
              )
            }
          />
        ))}
      </ul>
      {effects.message === null ? null : (
        <p role="status" className="text-muted-foreground">
          {effects.message}
        </p>
      )}
    </div>
  );
}

function EffectRow({
  operation,
  disabled,
  onRecord,
}: {
  operation: Operation;
  disabled: boolean;
  onRecord: (seen: Seen) => void;
}) {
  return (
    <li className="flex flex-wrap items-center justify-between gap-3 py-3">
      <p className="min-w-0 font-mono text-ui font-medium break-all">
        {operation.tool_id}
      </p>
      <div className="flex flex-wrap gap-2">
        {SEEN.map((seen) => (
          <Button
            key={seen}
            variant="outline"
            size="sm"
            disabled={disabled}
            onClick={() => onRecord(seen)}
          >
            {CHOICES[seen]}
          </Button>
        ))}
      </div>
    </li>
  );
}
