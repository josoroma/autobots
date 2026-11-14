import { HELD_INPUTS } from "@/lib/submit";
import { cn } from "@/lib/utils";

/**
 * Beside the inputs of a write whose outcome is unknown, which stay locked as they were sent until
 * an accepted reply or a reload (Decision 0027 D2).
 */
export function HeldNote({ className }: { className?: string }) {
  return (
    <p
      data-held-note="true"
      className={cn("text-muted-foreground text-[12.5px]", className)}
    >
      {HELD_INPUTS}
    </p>
  );
}
