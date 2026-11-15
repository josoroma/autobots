/**
 * The list filter the Experts and Workflows screens share (WBLD-09): one tab and one search matched
 * by name, with each tab's count. Where the state lives is the screen's: Workflows keeps it in the
 * URL and Experts in component state, as PRD-Studio EX-02 doesn't say where Expert filters live. The
 * tool catalog builds its URLs with `withParams` too. Pure and JSX-free, so `node --test` covers it.
 */

/** A list's chosen tab and its search as typed. */
export interface ListFilter<Tab extends string> {
  tab: Tab;
  search: string;
}

/** The form a search matches with: trimmed and lower-cased. */
export function searchNeedle(raw: string): string {
  return raw.trim().toLowerCase();
}

/** Whether a name holds the needle. An empty needle matches every name. */
export function matchesSearch(name: string, needle: string): boolean {
  return needle === "" || name.toLowerCase().includes(needle);
}

/** The items in the filter's tab whose name matches its search, in their order. */
export function filterList<T, Tab extends string>(
  items: readonly T[],
  filter: ListFilter<Tab>,
  inTab: (item: T, tab: Tab) => boolean,
  nameOf: (item: T) => string,
): T[] {
  const needle = searchNeedle(filter.search);
  return items.filter(
    (item) => inTab(item, filter.tab) && matchesSearch(nameOf(item), needle),
  );
}

/** How many items each tab holds, whatever the search, in the tabs' order. */
export function tabCounts<T, Tab extends string>(
  items: readonly T[],
  tabs: readonly Tab[],
  inTab: (item: T, tab: Tab) => boolean,
): ReadonlyMap<Tab, number> {
  return new Map(
    tabs.map((tab) => [tab, items.filter((item) => inTab(item, tab)).length]),
  );
}

/** The tab a value names, or the fallback for a missing or unknown one, as in a hand-edited URL. */
export function parseTab<Tab extends string>(
  value: string | null,
  tabs: readonly Tab[],
  fallback: Tab,
): Tab {
  return tabs.find((tab) => tab === value) ?? fallback;
}

/**
 * The page's URL with some search parameters changed: a null or empty value removes one, a set one
 * keeps its place, and the rest keep their order. With no parameters left it's the bare path.
 */
export function withParams(
  pathname: string,
  query: string,
  changes: Readonly<Record<string, string | null>>,
): string {
  const next = new URLSearchParams(query);
  for (const [key, value] of Object.entries(changes)) {
    if (value === null || value === "") next.delete(key);
    else next.set(key, value);
  }
  const rest = next.toString();
  return rest === "" ? pathname : `${pathname}?${rest}`;
}
