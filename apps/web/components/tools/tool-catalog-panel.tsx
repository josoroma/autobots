"use client";

import { listTools } from "@autobots/api-client";

import { CatalogToolbar } from "@/components/tools/catalog-toolbar";
import { ToolDialog } from "@/components/tools/tool-dialog";
import { ToolGroupSection } from "@/components/tools/tool-group-section";
import { useCatalogFilters } from "@/components/tools/use-catalog-filters";
import { LoadState } from "@/components/ui/load-state";
import { readOf } from "@/lib/load";
import { filterTools, groupTools } from "@/lib/tools/filters";
import { useResource } from "@/lib/use-resource";

/**
 * Where focus goes when a tool's dialog closes (PRD-Tool-Catalog TG-02, WTAP-13): the tool's link, or
 * for a deep link to a tool the filters hide, the list's first link, or else the catalog's search.
 */
function opener(toolId: string): HTMLElement | null {
  return (
    document.querySelector<HTMLAnchorElement>(
      `[data-tool="${CSS.escape(toolId)}"] a`,
    ) ??
    document.querySelector<HTMLAnchorElement>("[data-tool] a") ??
    document.querySelector<HTMLInputElement>(
      'form[aria-label="Filter tools"] input[type="search"]',
    )
  );
}

/**
 * The Tools page (PRD-Tool-Catalog TS-01 to TS-03). Every state is said in words; a badge never
 * stands for one alone. The filters live in the URL, and a tool's detail opens in a dialog over the
 * list (Decision 0026 G2).
 */
export function ToolCatalogPanel() {
  const filters = useCatalogFilters();
  const { state, pending, reload } = useResource(readOf(listTools));
  if (state.kind !== "ready") {
    return (
      <LoadState
        state={state}
        what="the tool catalog"
        onRetry={reload}
        pending={pending}
      />
    );
  }
  const catalog = state.value;
  const shown = filterTools(catalog.tools, filters.values);
  const selected = filters.selected;
  return (
    <div className="space-y-5">
      <CatalogToolbar
        catalog={catalog}
        filters={filters}
        shown={shown.length}
      />
      <div className="grid gap-6">
        <div className="min-w-0 space-y-5">
          {groupTools(catalog.groups, shown).map(({ group, tools }) => (
            <ToolGroupSection
              key={group.group}
              group={group}
              tools={tools}
              selected={selected}
              panelHref={filters.panelHref}
            />
          ))}
        </div>
        {selected === null ? null : (
          <ToolDialog
            key={selected}
            toolId={selected}
            onClosed={filters.close}
            returnFocus={() => opener(selected)}
          />
        )}
      </div>
    </div>
  );
}
