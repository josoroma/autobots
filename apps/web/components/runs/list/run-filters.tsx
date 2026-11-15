import type { RunList } from "@autobots/api-client";

import { Input, Select } from "@/components/ui/field";
import { PROFILE_NAME, profileChoice } from "@/lib/model-profile";
import { RUN_GROUPS, type RunFilters, type RunGroup } from "@/lib/runs/list";
import { cn } from "@/lib/utils";

/** RN-02: status groups with the server's counts, a goal or Expert filter, and a model filter. */
export function RunListFilters({
  filters,
  list,
  onChange,
}: {
  filters: RunFilters;
  list: RunList | null;
  onChange: (patch: Partial<RunFilters>) => void;
}) {
  return (
    <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
      <GroupButtons
        group={filters.group}
        counts={list?.counts ?? null}
        onChoose={(group) => onChange({ group })}
      />
      <span className="hidden flex-1 lg:block" />
      <label className="flex items-center gap-2 text-[13px]">
        <span className="sr-only">Filter by goal or Expert</span>
        <Input
          type="search"
          value={filters.query}
          onChange={(event) => onChange({ query: event.target.value })}
          placeholder="Filter by goal or Expert"
          className="h-8 w-full lg:w-64"
        />
      </label>
      <label className="flex items-center gap-2 text-[13px]">
        <span className="text-muted-foreground">Model</span>
        <Select
          value={filters.profile}
          onChange={(event) => {
            // A value that isn't a profile is ignored (PRD-Model-Providers MP-A08).
            const profile = profileChoice(event.target.value);
            if (profile !== null) onChange({ profile });
          }}
          className="h-8 w-40"
        >
          <option value="">Any model</option>
          {Object.entries(PROFILE_NAME).map(([id, name]) => (
            <option key={id} value={id}>
              {name}
            </option>
          ))}
        </Select>
      </label>
    </div>
  );
}

function GroupButtons({
  group,
  counts,
  onChoose,
}: {
  group: RunGroup;
  counts: RunList["counts"] | null;
  onChoose: (group: RunGroup) => void;
}) {
  return (
    <div
      role="group"
      aria-label="Status"
      className="bg-muted/60 inline-flex w-fit flex-wrap gap-0.5 rounded-lg p-[3px]"
    >
      {RUN_GROUPS.map((item) => (
        <button
          key={item.id}
          type="button"
          aria-pressed={group === item.id}
          data-group={item.id}
          onClick={() => onChoose(item.id)}
          className={cn(
            "text-foreground/80 inline-flex h-7 items-center gap-1.5 rounded-md border border-transparent px-3 text-[13px]",
            group === item.id &&
              "bg-background text-foreground border-border font-medium dark:bg-accent",
          )}
        >
          {item.label}{" "}
          <span className="tabular-nums">
            {counts === null ? "" : counts[item.id]}
          </span>
        </button>
      ))}
    </div>
  );
}
