import type { ToolCatalog } from "@autobots/api-client";

import type { CatalogFilters } from "@/components/tools/use-catalog-filters";
import { Input, Select } from "@/components/ui/field";
import { providersOf } from "@/lib/tools/filters";
import { useUrlDraft } from "@/lib/use-url-draft";
import {
  AVAILABILITY_FILTERS,
  AVAILABILITY_LABEL,
  PROVIDER_LABEL,
} from "@/lib/tools/text";

const TOOLBAR_LABEL =
  "flex w-full flex-col items-stretch gap-1 text-ui font-medium sm:w-auto sm:flex-row sm:items-center sm:gap-2 [&>span:first-child]:text-muted-foreground";

const trim = (raw: string): string => raw.trim();

/**
 * The search and the three filters, then how many tools show and the catalog's digest
 * (PRD-Tool-Catalog TS-01). The search box shows what was typed and follows the URL when it changes
 * from outside, such as the sidebar's Tools link (WTAP-15).
 */
export function CatalogToolbar({
  catalog,
  filters,
  shown,
}: {
  catalog: ToolCatalog;
  filters: CatalogFilters;
  /** How many tools the filters show. */
  shown: number;
}) {
  const { values, choose } = filters;
  const search = useUrlDraft(values.search, (q) => choose("q", q), {
    delayMs: 150,
    normalize: trim,
  });
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
      <form
        aria-label="Filter tools"
        className="flex flex-wrap items-center gap-x-4 gap-y-2"
        onSubmit={(event) => event.preventDefault()}
      >
        <label className={TOOLBAR_LABEL}>
          <span>Search</span>
          <Input
            type="search"
            value={search.value}
            onChange={(event) => search.change(event.target.value)}
            placeholder="Name, ID or description"
            className="h-8 w-full sm:w-56"
          />
        </label>
        <label className={TOOLBAR_LABEL}>
          <span>Group</span>
          <Select
            className="h-8 w-full sm:w-44"
            value={values.group}
            onChange={(event) => choose("group", event.target.value)}
          >
            <option value="">All groups</option>
            {catalog.groups.map((item) => (
              <option key={item.group} value={item.group}>
                {item.title}
              </option>
            ))}
          </Select>
        </label>
        <label className={TOOLBAR_LABEL}>
          <span>Availability</span>
          <Select
            className="h-8 w-full sm:w-52"
            value={values.availability}
            onChange={(event) => choose("availability", event.target.value)}
          >
            <option value="">Any availability</option>
            {AVAILABILITY_FILTERS.map((item) => (
              <option key={item} value={item}>
                {AVAILABILITY_LABEL[item]}
              </option>
            ))}
          </Select>
        </label>
        <label className={TOOLBAR_LABEL}>
          <span>Provider</span>
          <Select
            className="h-8 w-full sm:w-48"
            value={values.provider}
            onChange={(event) => choose("provider", event.target.value)}
          >
            <option value="">All providers</option>
            {providersOf(catalog.tools).map((item) => (
              <option key={item} value={item}>
                {PROVIDER_LABEL[item]}
              </option>
            ))}
          </Select>
        </label>
      </form>
      <p
        className="text-muted-foreground text-meta sm:ml-auto"
        data-field="digest"
      >
        {shown} of {catalog.tools.length} tools. Catalog{" "}
        <code className="font-mono">{catalog.catalog_digest.slice(0, 12)}</code>
        .
      </p>
    </div>
  );
}
