import { Input } from "@/components/ui/field";
import { EXPERT_FILTERS, type ExpertFilter } from "@/lib/experts/card";
import { cn } from "@/lib/utils";

/**
 * The Experts list's filter and search, kept in component state, as PRD-Studio EX-02 doesn't say
 * where they live (WBLD-09). Until the catalog is read the two class filters have no count and wait,
 * since no Expert can be called read only yet.
 */
export function ExpertFilters({
  filter,
  onFilter,
  counts,
  known,
  search,
  onSearch,
}: {
  filter: ExpertFilter;
  onFilter: (filter: ExpertFilter) => void;
  counts: ReadonlyMap<ExpertFilter, number>;
  /** The catalog is read, so the classes are known. */
  known: boolean;
  search: string;
  onSearch: (search: string) => void;
}) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
      <div
        role="group"
        aria-label="Show"
        className="bg-muted/60 inline-flex w-fit flex-wrap gap-0.5 rounded-lg p-[3px]"
      >
        {EXPERT_FILTERS.map(([id, label]) => {
          const waiting = !known && id !== "all";
          return (
            <button
              key={id}
              type="button"
              data-filter={id}
              aria-pressed={filter === id}
              disabled={waiting}
              onClick={() => onFilter(id)}
              className={cn(
                "text-foreground/80 inline-flex h-7 items-center gap-1.5 rounded-md border border-transparent px-3 text-[13px] disabled:opacity-50",
                filter === id &&
                  "bg-background text-foreground border-border font-medium dark:bg-accent",
              )}
            >
              {label}
              {waiting ? null : (
                <>
                  {" "}
                  <span className="tabular-nums">{counts.get(id) ?? 0}</span>
                </>
              )}
            </button>
          );
        })}
      </div>
      <span className="hidden flex-1 sm:block" />
      <label className="block">
        <span className="sr-only">Search Experts</span>
        <Input
          type="search"
          value={search}
          onChange={(event) => onSearch(event.target.value)}
          placeholder="Search Experts"
          className="h-8 w-full sm:w-60"
        />
      </label>
    </div>
  );
}
