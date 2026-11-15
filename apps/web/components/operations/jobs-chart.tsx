import { parseJobsChart } from "@autobots/api-client";
import { BarChart3 } from "lucide-react";

import { JobsPlot } from "@/components/operations/jobs-plot";
import { LoadState } from "@/components/ui/load-state";
import { useResource } from "@/lib/use-resource";

// PRD-Studio OP-03 and Decision 0022 D14: one read of the last 24 hours' job counts by outcome.
export function JobsChart() {
  const read = useResource("/api/v1/operations/jobs", parseJobsChart);
  const chart = read.state.kind === "ready" ? read.state.value : null;
  return (
    <section
      aria-labelledby="jobs-heading"
      data-field="jobs-chart"
      className="border-border space-y-3 rounded-xl border px-5 py-4"
    >
      <h2
        id="jobs-heading"
        className="flex items-center gap-2 text-sm font-semibold"
      >
        <BarChart3
          aria-hidden="true"
          className="text-muted-foreground size-4 shrink-0"
        />
        Jobs per hour, last 24 hours
      </h2>
      {chart === null ? (
        <LoadState
          state={read.state}
          what="job counts"
          onRetry={read.reload}
          pending={read.pending}
        />
      ) : (
        <JobsPlot chart={chart} />
      )}
    </section>
  );
}
