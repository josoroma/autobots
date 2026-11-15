import { listRuns, type RunList } from "@autobots/api-client";
import { useState } from "react";

import { load, readOf } from "@/lib/load";
import {
  runListQuery,
  withMore,
  type More,
  type RunFilters,
} from "@/lib/runs/list";

export interface MoreRuns {
  /** The first page with the pages Load more added to it, or null while there's no first page. */
  list: RunList | null;
  /** What Load more added to this first page, or null. */
  more: More | null;
  loadMore: () => Promise<void>;
}

/**
 * The pages Load more appends to the first page, which the page reads on the server for the URL's
 * filters (PRD-Studio RN-01, RN-02, R-67). A newer first page, read for other filters or after a
 * write, replaces them, so a page read for older filters is never appended to newer ones.
 */
export function useMoreRuns(
  first: RunList | null,
  filters: RunFilters,
): MoreRuns {
  const [more, setMore] = useState<More | null>(null);
  const shown = more?.base === first ? more : null;
  const list = first === null ? null : withMore(first, shown);

  async function loadMore(): Promise<void> {
    if (first === null || list?.next_cursor == null) return;
    const kept = shown ?? { base: first, runs: [], next: null, failure: null };
    setMore({ ...kept, loading: true });
    const loaded = await load(
      readOf(listRuns, runListQuery(filters, list.next_cursor)),
    );
    setMore(
      loaded.kind === "ready"
        ? {
            base: first,
            runs: [...kept.runs, ...loaded.value.runs],
            next: loaded.value,
            failure: null,
            loading: false,
          }
        : { ...kept, failure: loaded, loading: false },
    );
  }

  return { list, more: shown, loadMore };
}
