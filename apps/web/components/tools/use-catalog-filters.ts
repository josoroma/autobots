/**
 * The Tools page's filters and open tool, kept in the URL so a view can be linked (PRD-Tool-Catalog
 * TS-01). The detail opens in a modal dialog, and the URL keeps it as ?tool= (Decision 0026 G2).
 */
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { withParams } from "@/lib/list-filter";
import { readToolFilters, type ToolFilters } from "@/lib/tools/filters";

/** The URL parameter behind each filter. */
export type FilterParam = "q" | "group" | "availability" | "provider";

export interface CatalogFilters {
  values: ToolFilters;
  /** The tool whose dialog is open, or null. */
  selected: string | null;
  /** Sets one filter; an empty value removes it. */
  choose: (param: FilterParam, value: string) => void;
  /** The URL that opens a tool's dialog over this view. */
  panelHref: (toolId: string) => string;
  /** Leaves the dialog's URL, keeping the scroll position. */
  close: () => void;
}

export function useCatalogFilters(): CatalogFilters {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const query = params.toString();
  return {
    values: readToolFilters(params),
    selected: params.get("tool"),
    choose: (param, value) =>
      router.replace(withParams(pathname, query, { [param]: value })),
    panelHref: (toolId) => withParams(pathname, query, { tool: toolId }),
    close: () =>
      router.replace(withParams(pathname, query, { tool: null }), {
        scroll: false,
      }),
  };
}
