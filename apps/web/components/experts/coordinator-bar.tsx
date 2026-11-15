import { ArrowRight } from "lucide-react";

import { HeldNote } from "@/components/held-note";
import { Button } from "@/components/ui/button";

/** Starts a coordinator session among the Experts chosen on their cards (US-5.1). */
export function CoordinatorBar({
  routing,
  disabled,
  onStart,
}: {
  /** A coordinator session is held, so the Experts it names stay as sent. */
  routing: boolean;
  disabled: boolean;
  onStart: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-end gap-3">
      {routing ? <HeldNote /> : null}
      <Button className="rounded-full" onClick={onStart} disabled={disabled}>
        Start a coordinator session
        <ArrowRight aria-hidden="true" />
      </Button>
    </div>
  );
}
