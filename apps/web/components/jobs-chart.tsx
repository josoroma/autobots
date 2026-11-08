"use client";

import { parseJobsChart, type JobsChart as Chart } from "@autobots/api-client";
import { BarChart3 } from "lucide-react";
import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";

type Hour = Chart["hours"][number];
type SeriesKey = "succeeded" | "waited" | "in_progress" | "failed";

// PRD-Studio OP-03 and Decision 0022 D14. Each series means an outcome, so it wears its status token,
// never a categorical hue. Stacked in the order that keeps neighbours furthest apart under colour
// blindness (validated: worst adjacent ΔE 8.9 light, 10.4 dark). Waited and failed also carry a
// texture, at 45° and 135°, so no series depends on colour alone.
const SERIES: {
  key: SeriesKey;
  label: string;
  color: string;
  texture: number | null;
}[] = [
  {
    key: "succeeded",
    label: "Succeeded",
    color: "var(--success-text)",
    texture: null,
  },
  {
    key: "waited",
    label: "Waited for a person",
    color: "var(--attention)",
    texture: 45,
  },
  {
    key: "in_progress",
    label: "In progress",
    color: "var(--live-text)",
    texture: null,
  },
  {
    key: "failed",
    label: "Failed or cancelled",
    color: "var(--destructive)",
    texture: 135,
  },
];

const WIDTH = 720;
const HEIGHT = 200;
const LEFT = 32;
const BOTTOM = 22;
const TOP = 8;
const PLOT_W = WIDTH - LEFT - 4;
const PLOT_H = HEIGHT - TOP - BOTTOM;
const GAP = 2;

function fill(series: (typeof SERIES)[number]): string {
  return series.texture === null ? series.color : `url(#jobs-${series.key})`;
}

function total(hour: Hour): number {
  return SERIES.reduce((sum, series) => sum + hour[series.key], 0);
}

// A few round ticks up to the tallest bar, so the grid stays recessive.
function ticks(top: number): number[] {
  if (top <= 4) return Array.from({ length: top + 1 }, (_, index) => index);
  const step = Math.ceil(top / 4);
  return Array.from({ length: Math.ceil(top / step) + 1 }, (_, i) => i * step);
}

function Swatch({ series }: { series: (typeof SERIES)[number] }) {
  return (
    <svg aria-hidden="true" width="14" height="14" className="shrink-0">
      <rect width="14" height="14" rx="3" fill={fill(series)} />
    </svg>
  );
}

export function JobsChart() {
  const [chart, setChart] = useState<Chart | null>(null);
  const [failed, setFailed] = useState(false);
  const [active, setActive] = useState<number | null>(null);

  useEffect(() => {
    let live = true;
    fetch("/api/v1/operations/jobs", { cache: "no-store" })
      .then(async (reply) => {
        if (!live) return;
        if (reply.ok) setChart(parseJobsChart(await reply.json()));
        else {
          await reply.text();
          setFailed(true);
        }
      })
      .catch(() => {
        if (live) setFailed(true);
      });
    return () => {
      live = false;
    };
  }, []);

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
      {failed ? (
        <p className="text-muted-foreground text-sm">
          Job counts are unavailable.
        </p>
      ) : chart === null ? (
        <p className="text-muted-foreground text-sm">Loading job counts.</p>
      ) : (
        <JobsPlot chart={chart} active={active} setActive={setActive} />
      )}
    </section>
  );
}

function JobsPlot({
  chart,
  active,
  setActive,
}: {
  chart: Chart;
  active: number | null;
  setActive: (index: number | null) => void;
}) {
  const hours = chart.hours;
  const tallest = Math.max(1, ...hours.map(total));
  const scaleTop = ticks(tallest).at(-1) ?? tallest;
  const band = PLOT_W / hours.length;
  const barWidth = Math.max(4, band * 0.56);
  const y = (value: number) => TOP + PLOT_H - (value / scaleTop) * PLOT_H;
  const shown = active === null ? undefined : hours[active];
  const sums = SERIES.map((series) =>
    hours.reduce((sum, hour) => sum + hour[series.key], 0),
  );
  return (
    <div className="space-y-3">
      <p className="text-muted-foreground text-[12.5px]">
        Hours in {chart.timezone}. Each bar stacks one hour&apos;s jobs by how
        they ended; the table below gives the same counts.
      </p>
      <ul
        data-field="jobs-legend"
        className="flex flex-wrap gap-x-4 gap-y-1.5 text-[12.5px]"
      >
        {SERIES.map((series, index) => (
          <li
            key={series.key}
            data-series={series.key}
            className="flex items-center gap-1.5"
          >
            <Swatch series={series} />
            <span>
              {series.label}{" "}
              <span className="text-muted-foreground tabular-nums">
                {sums[index]}
              </span>
            </span>
          </li>
        ))}
      </ul>
      <div className="relative">
        <svg
          role="img"
          aria-labelledby="jobs-plot-title"
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          className="block h-auto w-full"
          onMouseLeave={() => setActive(null)}
        >
          <title id="jobs-plot-title">
            {`Jobs per hour over the last 24 hours: ${SERIES.map((series, index) => `${sums[index]} ${series.label.toLowerCase()}`).join(", ")}.`}
          </title>
          <defs>
            {SERIES.filter((series) => series.texture !== null).map(
              (series) => (
                <pattern
                  key={series.key}
                  id={`jobs-${series.key}`}
                  patternUnits="userSpaceOnUse"
                  width="6"
                  height="6"
                  patternTransform={`rotate(${series.texture})`}
                >
                  <rect width="6" height="6" fill={series.color} />
                  <line
                    x1="0"
                    y1="0"
                    x2="0"
                    y2="6"
                    stroke="var(--background)"
                    strokeOpacity="0.55"
                    strokeWidth="2"
                  />
                </pattern>
              ),
            )}
            {hours.map((hour, index) => {
              const x = LEFT + index * band + (band - barWidth) / 2;
              const top = y(total(hour));
              return (
                <clipPath key={hour.starts_at} id={`jobs-bar-${index}`}>
                  {/* Rounded at the data end only: the clip runs past the baseline. */}
                  <rect
                    x={x}
                    y={top}
                    width={barWidth}
                    height={TOP + PLOT_H - top + 6}
                    rx="4"
                  />
                </clipPath>
              );
            })}
          </defs>
          {ticks(tallest).map((tick) => (
            <g key={tick}>
              <line
                x1={LEFT}
                x2={WIDTH - 4}
                y1={y(tick)}
                y2={y(tick)}
                stroke="var(--border)"
                strokeWidth="1"
              />
              <text
                x={LEFT - 6}
                y={y(tick) + 3.5}
                textAnchor="end"
                fontSize="10"
                fill="var(--muted-foreground)"
              >
                {tick}
              </text>
            </g>
          ))}
          {hours.map((hour, index) => {
            const x = LEFT + index * band + (band - barWidth) / 2;
            let base = 0;
            return (
              <g key={hour.starts_at} data-hour={hour.hour}>
                {active === index ? (
                  <rect
                    x={LEFT + index * band}
                    y={TOP}
                    width={band}
                    height={PLOT_H}
                    fill="var(--muted)"
                  />
                ) : null}
                <g clipPath={`url(#jobs-bar-${index})`}>
                  {SERIES.map((series) => {
                    const value = hour[series.key];
                    if (value === 0) return null;
                    const lower = y(base);
                    base += value;
                    const upper = y(base);
                    // A surface gap between stacked segments.
                    const height = Math.max(lower - upper - GAP, 1);
                    return (
                      <rect
                        key={series.key}
                        x={x}
                        y={upper}
                        width={barWidth}
                        height={height}
                        fill={fill(series)}
                      />
                    );
                  })}
                </g>
                {index % 3 === 0 ? (
                  <text
                    x={LEFT + index * band + band / 2}
                    y={HEIGHT - 6}
                    textAnchor="middle"
                    fontSize="10"
                    fill="var(--muted-foreground)"
                  >
                    {hour.hour}
                  </text>
                ) : null}
                {/* The hover target is the whole hour, wider than its bar. */}
                <rect
                  x={LEFT + index * band}
                  y={TOP}
                  width={band}
                  height={PLOT_H}
                  fill="transparent"
                  onMouseEnter={() => setActive(index)}
                />
              </g>
            );
          })}
        </svg>
        {shown === undefined || active === null ? null : (
          <div
            aria-hidden="true"
            data-field="jobs-tooltip"
            className="bg-popover text-popover-foreground border-border pointer-events-none absolute top-0 z-10 rounded-lg border px-3 py-2 text-[12px] shadow-sm"
            style={{
              left: `${Math.min(((LEFT + (active + 0.5) * band) / WIDTH) * 100, 70)}%`,
            }}
          >
            <p className="font-medium tabular-nums">{shown.hour}</p>
            {SERIES.map((series) => (
              <p
                key={series.key}
                className="flex items-center gap-1.5 tabular-nums"
              >
                <Swatch series={series} />
                {series.label}: {shown[series.key]}
              </p>
            ))}
          </div>
        )}
      </div>
      <details data-field="jobs-table" className="text-[12.5px]">
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
            {hours.map((hour) => (
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
    </div>
  );
}
