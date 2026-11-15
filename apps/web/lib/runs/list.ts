/**
 * The runs list's pure parts (PRD-Studio RN-01 to RN-03): the read's path from its filters, a row's
 * state line and spend bar, and what Load more adds to one first page. Pure and JSX-free;
 * `components/runs/list/` shows them.
 */
import type { RunList } from "@autobots/api-client";

import type { LoadFailure } from "../load.ts";
import { RUN_STATUS_LABEL, stopReasonText } from "./status.ts";

// The API's run groups, by the counts it sends (the generator emits no type for the query).
export type RunGroup = keyof RunList["counts"];

export const RUN_GROUPS: readonly { id: RunGroup; label: string }[] = [
  { id: "all", label: "All" },
  { id: "active", label: "Active" },
  { id: "needs_you", label: "Needs you" },
  { id: "finished", label: "Finished" },
];

export interface RunFilters {
  group: RunGroup;
  query: string;
  profile: string;
}

/** The list's read. Defaults send no query string, so the first load is plain /api/v1/runs. */
export function runListPath(
  filters: RunFilters,
  cursor: string | null,
): string {
  const params = new URLSearchParams();
  if (filters.group !== "all") params.set("group", filters.group);
  if (filters.query.trim() !== "") params.set("q", filters.query.trim());
  if (filters.profile !== "") params.set("profile", filters.profile);
  if (cursor !== null) params.set("cursor", cursor);
  const search = params.toString();
  return search === "" ? "/api/v1/runs" : `/api/v1/runs?${search}`;
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
