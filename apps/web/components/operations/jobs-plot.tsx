import type { JobsChart } from "@autobots/api-client";
import { useState } from "react";

import { JobsBars } from "@/components/operations/jobs-bars";
import { JobsLegend } from "@/components/operations/jobs-legend";
import { JobsTable } from "@/components/operations/jobs-table";
import { JobsTooltip } from "@/components/operations/jobs-tooltip";
import { FRAME, layoutJobs, plotTitle, tooltipLeft } from "@/lib/jobs-layout";

/** The legend, the stacked bars with their hover layer, and the same counts as a table. */
export function JobsPlot({ chart }: { chart: JobsChart }) {
  const [active, setActive] = useState<number | null>(null);
  const layout = layoutJobs(chart.hours);
  const shown = active === null ? undefined : chart.hours[active];
  return (
    <div className="space-y-3">
      <p className="text-muted-foreground text-[12.5px]">
        Hours in {chart.timezone}. Each bar stacks one hour&apos;s jobs by how
        they ended; the table below gives the same counts.
      </p>
      <JobsLegend sums={layout.sums} />
      <div className="relative">
        <svg
          role="img"
          aria-labelledby="jobs-plot-title"
          viewBox={`0 0 ${FRAME.width} ${FRAME.height}`}
          className="block h-auto w-full"
          onMouseLeave={() => setActive(null)}
        >
          <title id="jobs-plot-title">{plotTitle(layout.sums)}</title>
          <JobsBars
            hours={chart.hours}
            layout={layout}
            active={active}
            onHover={setActive}
          />
        </svg>
        {shown === undefined || active === null ? null : (
          <JobsTooltip hour={shown} left={tooltipLeft(active, layout.band)} />
        )}
      </div>
      <JobsTable chart={chart} />
    </div>
  );
}
