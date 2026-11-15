import type { ApprovalCounts } from "@autobots/api-client";

import { cn } from "@/lib/utils";

export type Tab = "waiting" | "decided";

const TABS = [
  ["waiting", "Waiting"],
  ["decided", "Decided"],
] as const;

/**
 * Waiting and Decided with their counts (PRD-Studio AP-01). The tabs stay while a read loads or
 * has failed, and each shows its count once a read has one (WTAP-05).
 */
export function ApprovalTabs({
  tab,
  counts,
  onChoose,
}: {
  tab: Tab;
  counts: ApprovalCounts | null;
  onChoose: (tab: Tab) => void;
}) {
  return (
    <div
      role="group"
      aria-label="Requests"
      className="bg-muted/60 inline-flex w-fit gap-0.5 rounded-lg p-[3px]"
    >
      {TABS.map(([id, label]) => (
        <button
          key={id}
          type="button"
          data-tab={id}
          aria-pressed={tab === id}
          onClick={() => {
            if (id !== tab) onChoose(id);
          }}
          className={cn(
            "text-foreground/80 inline-flex h-7 items-center gap-1.5 rounded-md border border-transparent px-3 text-[13px]",
            tab === id &&
              "bg-background text-foreground border-border font-medium dark:bg-accent",
          )}
        >
          {label}
          {counts === null ? null : (
            <>
              {" "}
              <span className="tabular-nums">{counts[id]}</span>
            </>
          )}
        </button>
      ))}
    </div>
  );
}
