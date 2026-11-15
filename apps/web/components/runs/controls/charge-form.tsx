import { CircleDollarSign } from "lucide-react";

import type { ChargeWrites } from "@/components/runs/controls/use-run-controls";
import { HeldNote } from "@/components/held-note";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/field";

/** The owner records a charge seen in OpenRouter's own records, for the oldest open call. */
export function ChargeForm({
  openCalls,
  charge,
  busy,
}: {
  openCalls: number;
  charge: ChargeWrites;
  busy: boolean;
}) {
  return (
    <Card
      as="form"
      onSubmit={(event) => void charge.reconcile(event)}
      data-reconcile="true"
      className="border-attention/40 dark:bg-attention/5 space-y-3 p-4 text-sm"
    >
      <p className="flex items-start gap-2.5 leading-relaxed">
        <CircleDollarSign
          aria-hidden="true"
          className="text-attention mt-0.5 size-4 shrink-0"
        />
        <span>
          {openCalls === 1
            ? "One model call has"
            : `${openCalls} model calls have`}{" "}
          no settled charge. Look it up in OpenRouter&apos;s own records, since
          no one here can tell. Only the workspace owner can record it.
        </span>
      </p>
      <div className="space-y-1.5">
        <label htmlFor="model-call-charge" className="block font-medium">
          Charge seen, in US dollars
        </label>
        <div className="flex flex-wrap items-center gap-2">
          <Input
            id="model-call-charge"
            value={charge.value}
            readOnly={charge.held}
            onChange={(event) => charge.setValue(event.target.value)}
            inputMode="decimal"
            autoComplete="off"
            className="w-40 font-mono tabular-nums"
          />
          <Button type="submit" variant="outline" disabled={busy}>
            Record the charge
          </Button>
        </div>
        {charge.held ? <HeldNote /> : null}
      </div>
    </Card>
  );
}
