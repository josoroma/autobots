/**
 * The palette's search for what's typed (PRD-Studio SR-01, WCMP-05, WCMP-10). Typing sends one read
 * once it pauses, and a newer read aborts an older one. `current` says whether the results shown are
 * for the words typed now, since the last ones stay shown while a newer search is pending.
 */
import { search, type SearchResult } from "@autobots/api-client";

import { useMismatchLog } from "@/components/ui/load-state";
import {
  failureWords,
  readOf,
  worstFailure,
  type LoadFailure,
} from "@/lib/load";
import {
  SEARCH_DELAY_MS,
  SEARCH_WHAT,
  searchStatusText,
} from "@/lib/search-status";
import { useResource } from "@/lib/use-resource";

export interface Search {
  results: SearchResult[];
  /** No newer search is pending, so the results are for the words typed now. */
  current: boolean;
  failure: LoadFailure | null;
  status: string;
  /** The failure is an outage, so searching again may help. */
  retryable: boolean;
  pending: boolean;
  /** Counts settled searches, so a highlight chosen in an older one is reset. */
  settled: number;
  reload: () => void;
  /** Forgets every earlier search, so the same words typed again read again. */
  clear: () => void;
}

export function useSearch(query: string): Search {
  const term = query.trim();
  const read = useResource(term === "" ? null : readOf(search, { q: term }), {
    delayMs: SEARCH_DELAY_MS,
  });
  useMismatchLog(read.state);
  const results = read.state.kind === "ready" ? read.state.value.results : [];
  const failure = worstFailure([read.state]);
  return {
    results,
    current: !read.pending,
    failure,
    status: searchStatusText({
      idle: read.state.kind === "idle",
      searching: read.pending || read.state.kind === "loading",
      failure,
      count: results.length,
    }),
    retryable: failure !== null && failureWords(failure, SEARCH_WHAT).retry,
    pending: read.pending,
    settled: read.settled,
    reload: read.reload,
    clear: read.clear,
  };
}
