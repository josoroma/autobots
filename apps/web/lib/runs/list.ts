/**
 * The runs list's pure parts (PRD-Studio RN-01 to RN-03): the read's query from its filters, a row's
 * state line and spend bar, and what Load more adds to one first page. Pure and JSX-free;
 * `components/runs/list/` shows them.
 */
import type {
  ListRunsQuery,
  ModelProfileId,
  RunList,
} from "@autobots/api-client";

import type { LoadFailure } from "../load.ts";
import { RUN_STATUS_LABEL, stopReasonText } from "./status.ts";

// The API's run groups, as the list's query names them.
export type RunGroup = NonNullable<ListRunsQuery["group"]>;

export const RUN_GROUPS: readonly { id: RunGroup; label: string }[] = [
  { id: "all", label: "All" },
  { id: "active", label: "Active" },
  { id: "needs_you", label: "Needs you" },
  { id: "finished", label: "Finished" },
];

export interface RunFilters {
  group: RunGroup;
  query: string;
  /** A profile, or "" for any. */
  profile: ModelProfileId | "";
}

/** The list's query. Defaults are left out, so the first load is plain /api/v1/runs. */
export function runListQuery(
  filters: RunFilters,
  cursor: string | null,
): ListRunsQuery {
  const query = filters.query.trim();
  return {
    group: filters.group === "all" ? undefined : filters.group,
    q: query === "" ? undefined : query,
    profile: filters.profile === "" ? undefined : filters.profile,
    cursor: cursor ?? undefined,
  };
}

export type RunRow = RunList["runs"][number];

/** A row's state: why a failed run stopped, or how far a working run has got. */
export function stateLine(run: RunRow): string {
  const words = RUN_STATUS_LABEL[run.status];
  if (run.status === "failed" && run.stop_reason)
    return `${words} · ${stopReasonText(run.stop_reason)}`;
  if (
    (run.status === "running" || run.status === "verifying") &&
    run.tasks_total > 0
  )
    return `${words} · ${run.tasks_complete} of ${run.tasks_total}`;
  return words;
}

/** The spend bar's width: the whole percent of the limit spent, at most 100. */
export function spendShare(
  spentMicroUsd: number,
  limitMicroUsd: number,
): number {
  return limitMicroUsd > 0
    ? Math.min(100, Math.round((spentMicroUsd / limitMicroUsd) * 100))
    : 0;
}

/**
 * What Load more added to one first page: its rows, the newest page and why the last read failed. A
 * newer first page replaces it, so a page read for older filters is never appended to newer ones.
 */
export interface More {
  base: RunList;
  runs: RunRow[];
  next: RunList | null;
  failure: LoadFailure | null;
  loading: boolean;
}

export function withMore(base: RunList, more: More | null): RunList {
  return more?.next == null
    ? base
    : { ...more.next, runs: [...base.runs, ...more.runs] };
}
