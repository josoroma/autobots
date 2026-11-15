import { listRuns } from "@autobots/api-client";
import { useState } from "react";

import { load, readOf } from "@/lib/load";
import {
  runListQuery,
  withMore,
  type More,
  type RunFilters,
} from "@/lib/runs/list";
import { useResource } from "@/lib/use-resource";

/**
 * The runs list's read (PRD-Studio RN-01, RN-02): the first page for the current filters, and the
 * pages Load more appends to it. Typing in the filter sends one read once it pauses.
 */
export function useRunList() {
  const [filters, setFilters] = useState<RunFilters>({
    group: "all",
    query: "",
    profile: "",
  });
  const [more, setMore] = useState<More | null>(null);
  const { state, pending, reload } = useResource(
    readOf(listRuns, runListQuery(filters, null)),
    { delayMs: 150 },
  );
  const base = state.kind === "ready" ? state.value : null;
  const shown = more?.base === base ? more : null;
  const list = base === null ? null : withMore(base, shown);

  async function loadMore(): Promise<void> {
    if (base === null || list?.next_cursor == null) return;
    const kept = shown ?? { base, runs: [], next: null, failure: null };
    setMore({ ...kept, loading: true });
    const loaded = await load(
      readOf(listRuns, runListQuery(filters, list.next_cursor)),
    );
    setMore(
      loaded.kind === "ready"
        ? {
            base,
            runs: [...kept.runs, ...loaded.value.runs],
            next: loaded.value,
            failure: null,
            loading: false,
          }
        : { ...kept, failure: loaded, loading: false },
    );
  }

  const filter = (patch: Partial<RunFilters>) =>
    setFilters((current) => ({ ...current, ...patch }));
  return {
    filters,
    filter,
    state,
    pending,
    reload,
    list,
    more: shown,
    loadMore,
  };
}
