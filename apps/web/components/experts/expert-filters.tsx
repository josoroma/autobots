import { Input } from "@/components/ui/field";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { EXPERT_FILTERS, type ExpertFilter } from "@/lib/experts/card";

/**
 * The Experts list's filter and search (PRD-Studio EX-02), which the panel keeps in the URL (XWEB-13).
 * Until the catalog is read the two class filters have no count and wait, since no Expert can be
 * called read only yet.
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
      <SegmentedControl
        label="Show"
        dataKey="filter"
        wrap
        items={EXPERT_FILTERS.map(([id, label]) => {
          const waiting = !known && id !== "all";
          return waiting
            ? { id, label, disabled: true }
            : { id, label, disabled: false, count: counts.get(id) ?? 0 };
        })}
        value={filter}
        onChange={onFilter}
      />
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
