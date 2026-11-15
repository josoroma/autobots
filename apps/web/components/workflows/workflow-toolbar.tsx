import Link from "next/link";

import type { WorkflowFilter } from "@/components/workflows/use-workflow-filter";
import { Input } from "@/components/ui/field";
import { cn } from "@/lib/utils";
import { WORKFLOW_TABS, type WorkflowTab } from "@/lib/workflows/list";

/** The Workflows list's tabs, as links with their counts, and its search, both in the URL. */
export function WorkflowToolbar({
  filter,
  counts,
}: {
  filter: WorkflowFilter;
  counts: ReadonlyMap<WorkflowTab, number>;
}) {
  return (
    <div className="flex flex-wrap items-end gap-x-4 gap-y-2">
      <nav aria-label="Workflow tabs" className="flex gap-1">
        {WORKFLOW_TABS.map((item) => (
          <Link
            key={item.id}
            href={filter.href({ tab: item.id === "all" ? null : item.id })}
            scroll={false}
            aria-current={filter.tab === item.id ? "page" : undefined}
            data-tab={item.id}
            className={cn(
              "rounded-lg border px-3 py-1.5 text-[13px]",
              filter.tab === item.id
                ? "border-foreground font-medium"
                : "border-transparent",
            )}
          >
            {item.label}{" "}
            <span className="text-muted-foreground tabular-nums">
              {counts.get(item.id) ?? 0}
            </span>
          </Link>
        ))}
      </nav>
      <label className="ml-auto flex items-center gap-2 text-[13px]">
        <span className="text-muted-foreground">Search</span>
        <Input
          type="search"
          defaultValue={filter.search}
          placeholder="Workflow name"
          onChange={(event) => filter.replace({ q: event.target.value.trim() })}
          className="h-8 w-48"
        />
      </label>
    </div>
  );
}
