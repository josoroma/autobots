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

import { firstParam, parseTab, type SearchParam } from "../list-filter.ts";
import type { LoadFailure } from "../load-failure.ts";
import { profileChoice } from "../model-profile.ts";
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

const RUN_GROUP_IDS: readonly RunGroup[] = RUN_GROUPS.map((item) => item.id);

/**
 * The list's filters from the page's URL (XWEB-13). A group or profile the list doesn't offer, as a
 * hand-edited URL can name, reads as none (PRD-Model-Providers MP-A08).
 */
export function runFiltersFrom(
  params: Readonly<Record<string, SearchParam>>,
): RunFilters {
  return {
    group: parseTab(firstParam(params.group), RUN_GROUP_IDS, "all"),
    query: firstParam(params.q) ?? "",
    profile: profileChoice(firstParam(params.profile) ?? "") ?? "",
  };
}

/** The filters a URL query names, read as `runFiltersFrom` reads a page's parameters. */
export function runFiltersFromQuery(query: string): RunFilters {
  return runFiltersFrom(Object.fromEntries(new URLSearchParams(query)));
}

/**
 * The filters as a URL query, always in one order, so equal filters give equal strings. A filter at
 * its default is left out, so the plain list is plain /runs. The search is trimmed for the URL, or
 * kept as typed for what the search box shows.
 */
export function runFilterQuery(filters: RunFilters, asTyped = false): string {
  const params = new URLSearchParams();
  if (filters.group !== "all") params.set("group", filters.group);
  const query = asTyped ? filters.query : filters.query.trim();
  if (query !== "") params.set("q", query);
  if (filters.profile !== "") params.set("profile", filters.profile);
  return params.toString();
}

/**
 * A draft of the filters, as the search box holds it, in the form the URL keeps: the search
 * trimmed. Equal for a page's own filters, so opening the list writes nothing.
 */
export function runFilterQueryForUrl(draft: string): string {
  return runFilterQuery(runFiltersFromQuery(draft));
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

/**
 * The rows of a first page and the pages added to it, each run once. A run in the first page keeps
 * that row, as the newest server render, and a repeat later is left out.
 */
export function mergeRuns(
  first: readonly RunRow[],
  more: readonly RunRow[],
): RunRow[] {
  const seen = new Set<string>();
  return [...first, ...more].filter((run) => {
    if (seen.has(run.id)) return false;
    seen.add(run.id);
    return true;
  });
}

export function withMore(base: RunList, more: More | null): RunList {
  const runs = mergeRuns(base.runs, more?.next == null ? [] : more.runs);
  if (more?.next == null)
    return runs.length === base.runs.length ? base : { ...base, runs };
  return { ...more.next, runs };
}
