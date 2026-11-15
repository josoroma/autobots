import type { RunList } from "@autobots/api-client";
import Link from "next/link";

import { StateLine } from "@/components/runs/run-state";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { LoadEmpty, LoadState } from "@/components/ui/load-state";
import { spendOf } from "@/lib/budget";
import { formatInstant, formatUsd } from "@/lib/format";
import { profileName } from "@/lib/model-profile";
import { spendShare, stateLine, type More, type RunRow } from "@/lib/runs/list";
import { cn } from "@/lib/utils";

const COLUMNS = "lg:grid-cols-[minmax(0,1fr)_12rem_7rem_9rem_9rem] lg:gap-x-5";

/** The page of runs, or why there are none, with Load more under it. */
export function RunRows({
  list,
  more,
  selected,
  onMore,
  onSelect,
}: {
  list: RunList;
  more: More | null;
  selected: string | null;
  onMore: () => void;
  /** Opens a run's panel. */
  onSelect: (runId: string) => void;
}) {
  if (list.runs.length === 0) return <NoRuns all={list.counts.all} />;
  return (
    <div>
      {/* Column names for sighted readers; each row says its own facts in words. */}
      <div
        aria-hidden="true"
        className={cn(
          COLUMNS,
          "text-muted-foreground hidden border-b px-3 pb-2.5 text-meta font-medium lg:grid",
        )}
      >
        <span>Goal</span>
        <span>State</span>
        <span>Models</span>
        <span className="text-right">Spend</span>
        <span className="text-right">Started</span>
      </div>
      <ul className="divide-border divide-y border-b text-body max-lg:border-t">
        {list.runs.map((run) => (
          <Row
            key={run.id}
            run={run}
            selected={run.id === selected}
            onSelect={onSelect}
          />
        ))}
      </ul>
      <div className="mt-4 flex items-center gap-3 text-meta">
        <span data-state="shown" className="text-muted-foreground">
          Showing {list.runs.length} of {list.total}
        </span>
        <span className="flex-1" />
        {list.has_more ? (
          <Button
            variant="outline"
            size="sm"
            disabled={more?.loading === true}
            onClick={onMore}
          >
            Load more
          </Button>
        ) : null}
      </div>
      {more?.failure == null ? null : (
        <LoadState state={more.failure} what="more runs" className="mt-3" />
      )}
    </div>
  );
}

function NoRuns({ all }: { all: number }) {
  return (
    <Card className="border-dashed">
      <LoadEmpty>
        {all === 0 ? (
          <>
            This workspace has no runs yet. Start one from{" "}
            <Link href="/" className="font-medium underline">
              Home
            </Link>
            .
          </>
        ) : (
          "No runs match these filters."
        )}
      </LoadEmpty>
    </Card>
  );
}

function Row({
  run,
  selected,
  onSelect,
}: {
  run: RunRow;
  selected: boolean;
  onSelect: (runId: string) => void;
}) {
  const goal = run.goal_summary === "" ? "Untitled run" : run.goal_summary;
  return (
    <li
      data-run={run.id}
      data-status={run.status}
      className={cn(
        COLUMNS,
        "grid gap-x-6 gap-y-1.5 px-3 py-3 lg:min-h-[56px] lg:items-center lg:py-2",
      )}
    >
      <div className="min-w-0">
        <Link
          href={`/runs/${run.id}`}
          className="text-foreground font-medium break-words underline-offset-4 hover:underline"
        >
          {goal}
        </Link>
        <RowLabel
          run={run}
          goal={goal}
          selected={selected}
          onSelect={onSelect}
        />
      </div>
      <StateLine status={run.status} text={stateLine(run)} />
      <span
        data-field="models"
        className="text-muted-foreground font-mono text-xs"
      >
        <span className="lg:sr-only">Models </span>
        {run.profiles.length === 0
          ? "—"
          : run.profiles.map(profileName).join(" · ")}
      </span>
      <Spend run={run} />
      <span className="text-muted-foreground tabular-nums lg:text-right">
        <span className="lg:sr-only">Started </span>
        {formatInstant(run.created_at)}
      </span>
    </li>
  );
}

// RN-04: Details opens the run's panel under the list, and the address keeps it open with the
// list's filters.
function RowLabel({
  run,
  goal,
  selected,
  onSelect,
}: {
  run: RunRow;
  goal: string;
  selected: boolean;
  onSelect: (runId: string) => void;
}) {
  return (
    <span
      data-field="label"
      className="text-muted-foreground mt-0.5 block text-xs"
    >
      {run.label ?? "Goal"}
      {run.parent_run_id === null ? null : " · A child run"}
      {" · "}
      <button
        type="button"
        onClick={() => onSelect(run.id)}
        aria-expanded={selected}
        aria-controls={selected ? "run-panel" : undefined}
        aria-label={`Details for ${goal}`}
        data-field="details"
        className="text-foreground underline underline-offset-4"
      >
        Details
      </button>
    </span>
  );
}

// PRD-Studio RN-03: "≈" while a reservation is outstanding or a charge went unreported.
function Spend({ run }: { run: RunRow }) {
  const { micro: spent, estimated } = spendOf(
    run.charged_micro_usd,
    run.reserved_micro_usd,
    run.unreported,
  );
  return (
    <span data-field="spend" className="block lg:text-right">
      <span className="tabular-nums">
        {estimated ? (
          <>
            <span aria-hidden="true">≈ </span>
            <span className="sr-only">About </span>
          </>
        ) : null}
        {formatUsd(spent)}
      </span>
      <span className="text-muted-foreground block text-xs tabular-nums">
        {estimated ? "estimated, " : ""}of {formatUsd(run.limit_micro_usd)}
      </span>
      <span
        aria-hidden="true"
        className="bg-muted mt-1 block h-1 w-full overflow-hidden rounded-full lg:ml-auto lg:w-24"
      >
        <span
          className="bg-foreground/70 block h-full rounded-full"
          style={{ width: `${spendShare(spent, run.limit_micro_usd)}%` }}
        />
      </span>
    </span>
  );
}
