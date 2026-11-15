import type { RunList } from "@autobots/api-client";

import { Input, Select } from "@/components/ui/field";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { PROFILE_NAME, profileChoice } from "@/lib/model-profile";
import { RUN_GROUPS, type RunFilters, type RunGroup } from "@/lib/runs/list";

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
      <label className="flex items-center gap-2 text-ui">
        <span className="sr-only">Filter by goal or Expert</span>
        <Input
          type="search"
          value={filters.query}
          onChange={(event) => onChange({ query: event.target.value })}
          placeholder="Filter by goal or Expert"
          className="h-8 w-full lg:w-64"
        />
      </label>
      <label className="flex items-center gap-2 text-ui">
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
    <SegmentedControl
      label="Status"
      dataKey="group"
      wrap
      items={RUN_GROUPS.map((item) => ({
        id: item.id,
        label: item.label,
        count: counts === null ? "" : counts[item.id],
      }))}
      value={group}
      onChange={onChoose}
    />
  );
}
