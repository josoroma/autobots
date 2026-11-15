import type { ApprovalView } from "@autobots/api-client";

import { outcomeText } from "@/lib/approval-text";
import { untilDeadline } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
 * One tab's requests beside the selected one (PRD-Studio AP-02). The list is one tab stop, on the
 * selected request, and `data-approval-item` is how the arrow keys find where focus is.
 */
export function ApprovalList({
  approvals,
  selected,
  waiting,
  now,
  onSelect,
}: {
  approvals: readonly ApprovalView[];
  selected: string | null;
  waiting: boolean;
  now: number;
  onSelect: (id: string) => void;
}) {
  return (
    <ul
      aria-label={waiting ? "Waiting requests" : "Decided requests"}
      className="divide-border h-fit divide-y overflow-hidden rounded-xl border"
    >
      {approvals.map((approval) => (
        <li key={approval.id}>
          <button
            type="button"
            data-approval-item={approval.id}
            aria-current={approval.id === selected ? "true" : undefined}
            tabIndex={approval.id === selected ? 0 : -1}
            onClick={() => onSelect(approval.id)}
            className={cn(
              "hover:bg-accent/60 block w-full border-l-2 border-transparent px-3.5 py-3 text-left text-body",
              approval.id === selected &&
                "border-l-attention bg-background font-medium dark:bg-accent",
            )}
          >
            <span className="block break-words">
              {approval.tool_id}, version {approval.tool_version}
            </span>
            <span className="text-muted-foreground block text-xs break-words">
              {approval.run_goal ?? "Run goal not recorded"}
            </span>
            <span className="text-muted-foreground block text-xs">
              {waiting
                ? `Expires ${untilDeadline(approval.expires_at, now)}`
                : outcomeText(approval.status)}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
