import type { JobsChart } from "@autobots/api-client";

import { SERIES } from "@/lib/jobs-layout";
import { cn } from "@/lib/utils";

/** The same counts as a text table, the plot's alternative (PRD-Studio OP-03). */
export function JobsTable({ chart }: { chart: JobsChart }) {
  return (
    <details data-field="jobs-table" className="text-meta">
      <summary className="cursor-pointer font-medium">
        Table of the same counts
      </summary>
      <table className="mt-2 w-full table-fixed border-collapse tabular-nums">
        <caption className="sr-only">
          Jobs per hour over the last 24 hours, in {chart.timezone}
        </caption>
        <thead>
          <tr className="text-muted-foreground border-b text-left">
            <th scope="col" className="py-1.5 pr-2 font-medium">
              Hour
            </th>
            {SERIES.map((series) => (
              <th
                key={series.key}
                scope="col"
                className="py-1.5 pr-2 text-right font-medium break-words"
              >
                {series.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {chart.hours.map((hour) => (
            <tr
              key={hour.starts_at}
              data-row={hour.hour}
              className="border-border border-b"
            >
              <th scope="row" className="py-1 pr-2 text-left font-normal">
                {hour.hour}
              </th>
              {SERIES.map((series) => (
                <td
                  key={series.key}
                  data-series={series.key}
                  className={cn(
                    "py-1 pr-2 text-right",
                    hour[series.key] === 0 && "text-muted-foreground",
                  )}
                >
                  {hour[series.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}
