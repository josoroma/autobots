/**
 * The search palette's status line (PRD-Studio SR-01, WCMP-05, WCMP-10): how to start, that it's
 * searching, how many results were found, or why the search failed, never that nothing matches when
 * it couldn't look. Pure and JSX-free, so `node --test` covers it.
 */
import { failureWords, type LoadFailure } from "./load.ts";
import { counted } from "./plural.ts";

/** What a failed search names, in the shared failure words. */
export const SEARCH_WHAT = "search results";

/** Typing sends one read once it pauses this long. */
export const SEARCH_DELAY_MS = 150;

export interface SearchPhase {
  /** Nothing has been typed. */
  idle: boolean;
  /** A read for the current words hasn't settled. */
  searching: boolean;
  failure: LoadFailure | null;
  count: number;
}

export function searchStatusText(phase: SearchPhase): string {
  if (phase.idle)
    return "Type to search. ↑ ↓ to move, ↵ to open, Esc to close.";
  if (phase.searching) return "Searching.";
  if (phase.failure !== null) {
    return failureWords(phase.failure, SEARCH_WHAT).words;
  }
  return phase.count === 0
    ? "Nothing in this workspace matches."
    : `${counted(phase.count, "result", "results")}.`;
}
