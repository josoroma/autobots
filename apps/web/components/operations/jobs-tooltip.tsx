import type { JobHour } from "@autobots/api-client";

import { Swatch } from "@/components/operations/jobs-legend";
import { SERIES } from "@/lib/jobs-layout";

/**
 * The hovered hour and its counts. Hidden from assistive technology, since the table below gives
 * the same counts.
 */
export function JobsTooltip({ hour, left }: { hour: JobHour; left: string }) {
  return (
    <div
      aria-hidden="true"
      data-field="jobs-tooltip"
      className="bg-popover text-popover-foreground border-border pointer-events-none absolute top-0 z-10 rounded-lg border px-3 py-2 text-caption shadow-sm"
      style={{ left }}
    >
      <p className="font-medium tabular-nums">{hour.hour}</p>
      {SERIES.map((series) => (
        <p key={series.key} className="flex items-center gap-1.5 tabular-nums">
          <Swatch series={series} />
          {series.label}: {hour[series.key]}
        </p>
      ))}
    </div>
  );
}
