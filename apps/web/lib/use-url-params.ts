/**
 * A list's filters and selection in the page's URL (XWEB-13).
 *
 * A change the server reads, such as the run list's filters, renders the page again on the server
 * (R-67). Its URL is built from what the screen intends, never from the address bar, which still
 * shows the previous URL while that page is on its way, so a second change made within one round
 * trip doesn't undo the first.
 *
 * A change only the screen reads, such as a selection or a filter over a list already in the
 * browser, replaces the URL in place with no request. The address bar holds it at once, so the next
 * such change starts from it. Next.js keeps `useSearchParams` in step with both.
 */
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { withParams } from "@/lib/list-filter";

export type UrlChanges = Readonly<Record<string, string | null>>;

export interface UrlParams {
  /** A parameter's value, or null. */
  get: (name: string) => string | null;
  /**
   * Shows this page with `query`, which the screen builds from what it intends, with `changes`
   * made to it, and renders it again on the server, which reads for it.
   */
  navigate: (query: string, changes?: UrlChanges) => void;
  /** Replaces the URL in place, with no request: null or empty removes a parameter. */
  replace: (changes: UrlChanges) => void;
}

export function useUrlParams(): UrlParams {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  return {
    get: (name) => params.get(name),
    navigate: (query, changes = {}) =>
      router.replace(withParams(pathname, query, changes), { scroll: false }),
    replace: (changes) =>
      window.history.replaceState(
        null,
        "",
        withParams(
          window.location.pathname,
          window.location.search.slice(1),
          changes,
        ),
      ),
  };
}
