import { INNER_BOX } from "@/components/ui/card";
import { expansionText } from "@/lib/experts/grants";
import { cn } from "@/lib/utils";

/** The explicit list a save records, said as it changes (PRD-Tool-Catalog TC-06). */
export function GrantSummary({
  granted,
  groups,
}: {
  granted: readonly string[];
  groups: readonly string[];
}) {
  return (
    <p
      className={cn(INNER_BOX, "text-sm wrap-anywhere")}
      data-field="expansion"
      aria-live="polite"
    >
      {expansionText(granted, groups)}
    </p>
  );
}
