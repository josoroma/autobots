import type { LocalStatus } from "@autobots/api-client";
import { Check, CircleAlert, RotateCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  holdText,
  passingText,
  verdictText,
  workersText,
} from "@/lib/operations-text";
import { cn } from "@/lib/utils";

/**
 * PRD-Studio OP-01: the verdict sentence, the counts behind it from the checks shown below, and
 * Check again, which reads the status again.
 */
export function VerdictBanner({
  status,
  onCheckAgain,
}: {
  status: LocalStatus;
  onCheckAgain: () => void;
}) {
  const ready = status.ready;
  return (
    <section
      className={cn(
        "flex flex-wrap items-center gap-4 rounded-xl border px-5 py-4",
        ready
          ? "border-success-text/35 dark:bg-success-text/5"
          : "border-destructive/40 dark:bg-destructive/5",
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          "grid size-9 shrink-0 place-items-center rounded-full border",
          ready
            ? "text-success-text border-success-text/35 dark:bg-success-text/15 dark:border-transparent"
            : "text-destructive border-destructive/40 dark:bg-destructive/15 dark:border-transparent",
        )}
      >
        {ready ? (
          <Check className="size-4" strokeWidth={2.25} />
        ) : (
          <CircleAlert className="size-4" strokeWidth={2.25} />
        )}
      </span>
      <div className="min-w-0 flex-1 space-y-1">
        <p
          role="status"
          className="font-serif text-[21px] leading-snug tracking-[-0.01em]"
        >
          {verdictText(ready)}
        </p>
        <p
          data-field="verdict"
          className="text-muted-foreground text-[13px] tabular-nums"
        >
          <span data-field="checks-passing">
            {passingText(status.conditions)}
          </span>
          {" · "}
          <span data-field="workers">{workersText(status.values.workers)}</span>
          {" · "}
          <span data-field="hold">{holdText(status.conditions)}</span>
        </p>
      </div>
      <Button variant="outline" size="sm" onClick={onCheckAgain}>
        <RotateCw aria-hidden="true" />
        Check again
      </Button>
    </section>
  );
}
