import Link from "next/link";

import type { WorkflowFilter } from "@/components/workflows/use-workflow-filter";
import { Input } from "@/components/ui/field";
import { useUrlDraft } from "@/lib/use-url-draft";
import { cn } from "@/lib/utils";
import { WORKFLOW_TABS, type WorkflowTab } from "@/lib/workflows/list";

const trim = (raw: string): string => raw.trim();

/**
 * The Workflows list's tabs, as links with their counts, and its search, both in the URL. The search
 * box shows what was typed and follows the URL when it changes from outside (WTAP-15).
 */
export function WorkflowToolbar({
  filter,
  counts,
}: {
  filter: WorkflowFilter;
  counts: ReadonlyMap<WorkflowTab, number>;
}) {
  const search = useUrlDraft(filter.search, (q) => filter.replace({ q }), {
    delayMs: 150,
    normalize: trim,
  });
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
              "rounded-lg border px-3 py-1.5 text-ui",
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
      <label className="ml-auto flex items-center gap-2 text-ui">
        <span className="text-muted-foreground">Search</span>
        <Input
          type="search"
          value={search.value}
          placeholder="Workflow name"
          onChange={(event) => search.change(event.target.value)}
          className="h-8 w-48"
        />
      </label>
    </div>
  );
}
