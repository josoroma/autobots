import {
  SERIES,
  seriesFill,
  type Counts,
  type Series,
} from "@/lib/jobs-layout";

/** A series' fill as a small square, beside its words. */
export function Swatch({ series }: { series: Series }) {
  return (
    <svg aria-hidden="true" width="14" height="14" className="shrink-0">
      <rect width="14" height="14" rx="3" fill={seriesFill(series)} />
    </svg>
  );
}

/** Each series with its total over the 24 hours. */
export function JobsLegend({ sums }: { sums: Counts }) {
  return (
    <ul
      data-field="jobs-legend"
      className="flex flex-wrap gap-x-4 gap-y-1.5 text-[12.5px]"
    >
      {SERIES.map((series) => (
        <li
          key={series.key}
          data-series={series.key}
          className="flex items-center gap-1.5"
        >
          <Swatch series={series} />
          <span>
            {series.label}{" "}
            <span className="text-muted-foreground tabular-nums">
              {sums[series.key]}
            </span>
          </span>
        </li>
      ))}
    </ul>
  );
}
