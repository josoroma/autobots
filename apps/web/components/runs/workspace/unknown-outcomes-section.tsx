import type { RunWorkspace } from "@autobots/api-client";
import { TriangleAlert } from "lucide-react";
import { memo } from "react";

import { UnknownEffects } from "@/components/runs/effects/unknown-effects";
import { Card } from "@/components/ui/card";

/** Effects that may or may not have happened, which a person settles before the run resumes. */
export const UnknownOutcomesSection = memo(function UnknownOutcomesSection({
  runId,
  operations,
  onResolved,
}: {
  runId: string;
  operations: RunWorkspace["unknown_operations"];
  onResolved: () => void;
}) {
  if (operations.length === 0) return null;
  return (
    <Card
      aria-labelledby="unknown-heading"
      className="border-attention/40 dark:bg-attention/5 space-y-3"
    >
      <h2
        id="unknown-heading"
        className="flex items-center gap-2 text-sm font-semibold"
      >
        <TriangleAlert
          aria-hidden="true"
          className="text-attention size-4 shrink-0"
        />
        Unknown outcomes
      </h2>
      <UnknownEffects
        runId={runId}
        operations={operations}
        onResolved={onResolved}
      />
    </Card>
  );
});
