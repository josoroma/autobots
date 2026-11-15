import { Check, Lock } from "lucide-react";

import { Button } from "@/components/ui/button";
import { INNER_BOX } from "@/components/ui/card";
import type { Decision } from "@/lib/approval-shortcut";
import { cn } from "@/lib/utils";

/**
 * What each decision does, and its buttons with their shortcuts (PRD-Studio AP-04). The service
 * makes the decision; these only ask for it.
 */
export function DecisionBar({
  onDecide,
}: {
  onDecide: (decision: Decision) => void;
}) {
  return (
    <>
      <p className={cn(INNER_BOX, "flex items-start gap-3 text-[13.5px]")}>
        <Lock
          aria-hidden="true"
          className="text-muted-foreground mt-0.5 size-4 shrink-0"
        />
        <span>
          <span className="font-semibold">
            Approving releases only this exact request.
          </span>{" "}
          <span className="text-muted-foreground">
            Rejecting lets the run replan or fail, and this request won&apos;t
            run.
          </span>
        </span>
      </p>
      <div className="flex flex-wrap items-center gap-2.5">
        <Button size="lg" onClick={() => onDecide("approve")}>
          <Check aria-hidden="true" />
          Approve
        </Button>
        <Button size="lg" variant="outline" onClick={() => onDecide("reject")}>
          Reject
        </Button>
        <span className="text-muted-foreground ml-auto text-[12.5px]">
          Approve ⌘↵ · Reject ⌘⌫, each pressed twice · J and K move
        </span>
      </div>
    </>
  );
}
