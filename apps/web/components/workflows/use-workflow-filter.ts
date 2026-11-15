/**
 * The Workflows list's tab, search, chosen workflow and previewed version, kept in the URL so a view
 * survives a reload and Back and can be linked (PRD-Studio WF-01, WF-03).
 */
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { parseTab, withParams, type ListFilter } from "@/lib/list-filter";
import { WORKFLOW_TAB_IDS, type WorkflowTab } from "@/lib/workflows/list";

export interface WorkflowFilter extends ListFilter<WorkflowTab> {
  /** The workflow whose preview shows, or null. */
  selected: string | null;
  /** The version the preview was asked for, or null for its default. */
  version: string | null;
  /** This page's URL with some parameters changed; null or empty removes one. */
  href: (changes: Readonly<Record<string, string | null>>) => string;
  /** Replaces the URL, keeping the scroll position. */
  replace: (changes: Readonly<Record<string, string | null>>) => void;
}

export function useWorkflowFilter(): WorkflowFilter {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const href = (changes: Readonly<Record<string, string | null>>): string =>
    withParams(pathname, params.toString(), changes);
  return {
    tab: parseTab(params.get("tab"), WORKFLOW_TAB_IDS, "all"),
    search: params.get("q") ?? "",
    selected: params.get("workflow"),
    version: params.get("version"),
    href,
    replace: (changes) => router.replace(href(changes), { scroll: false }),
  };
}
