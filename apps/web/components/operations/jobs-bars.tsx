import type { JobHour } from "@autobots/api-client";

import {
  FRAME,
  patternId,
  SERIES,
  type Bar,
  type JobsLayout,
} from "@/lib/jobs-layout";

const BASELINE = FRAME.top + FRAME.plotHeight;
const LABEL = { fontSize: "10", fill: "var(--muted-foreground)" } as const;

function clipId(index: number): string {
  return `jobs-bar-${index}`;
}

/** The textures for waited and failed, and each bar's clip, rounded at the data end only. */
function JobsDefs({ layout }: { layout: JobsLayout }) {
  return (
    <defs>
      {SERIES.map((series) =>
        series.texture === null ? null : (
          <pattern
            key={series.key}
            id={patternId(series.key)}
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
      {layout.bars.map((bar) => (
        <clipPath key={bar.index} id={clipId(bar.index)}>
          {/* The clip runs past the baseline, so only the top corners are rounded. */}
          <rect
            x={bar.x}
            y={bar.top}
            width={bar.width}
            height={BASELINE - bar.top + 6}
            rx="4"
          />
        </clipPath>
      ))}
    </defs>
  );
}

function JobsGrid({ layout }: { layout: JobsLayout }) {
  return layout.ticks.map((tick) => (
    <g key={tick.value}>
      <line
        x1={FRAME.left}
        x2={FRAME.width - 4}
        y1={tick.y}
        y2={tick.y}
        stroke="var(--border)"
        strokeWidth="1"
      />
      <text x={FRAME.left - 6} y={tick.y + 3.5} textAnchor="end" {...LABEL}>
        {tick.value}
      </text>
    </g>
  ));
}

function JobsBar({
  bar,
  hour,
  band,
  active,
  onHover,
}: {
  bar: Bar;
  hour: JobHour;
  band: number;
  active: boolean;
  onHover: () => void;
}) {
  const area = {
    x: bar.bandX,
    y: FRAME.top,
    width: band,
    height: FRAME.plotHeight,
  };
  return (
    <g data-hour={hour.hour}>
      {active ? <rect {...area} fill="var(--muted)" /> : null}
      <g clipPath={`url(#${clipId(bar.index)})`}>
        {bar.segments.map((segment) => (
          <rect
            key={segment.key}
            x={bar.x}
            y={segment.y}
            width={bar.width}
            height={segment.height}
            fill={segment.fill}
          />
        ))}
      </g>
      {bar.index % 3 === 0 ? (
        <text
          x={bar.labelX}
          y={FRAME.height - 6}
          textAnchor="middle"
          {...LABEL}
        >
          {hour.hour}
        </text>
      ) : null}
      {/* The hover target is the whole hour, wider than its bar. */}
      <rect {...area} fill="transparent" onMouseEnter={onHover} />
    </g>
  );
}

/** The stacked bars, the grid and the hour labels, drawn from the layout. */
export function JobsBars({
  hours,
  layout,
  active,
  onHover,
}: {
  hours: readonly JobHour[];
  layout: JobsLayout;
  active: number | null;
  onHover: (index: number) => void;
}) {
  return (
    <>
      <JobsDefs layout={layout} />
      <JobsGrid layout={layout} />
      {layout.bars.map((bar) => {
        const hour = hours[bar.index];
        return hour === undefined ? null : (
          <JobsBar
            key={hour.starts_at}
            bar={bar}
            hour={hour}
            band={layout.band}
            active={active === bar.index}
            onHover={() => onHover(bar.index)}
          />
        );
      })}
    </>
  );
}
