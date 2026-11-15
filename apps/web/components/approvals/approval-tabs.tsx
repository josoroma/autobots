import type { ApprovalCounts } from "@autobots/api-client";

import { SegmentedControl } from "@/components/ui/segmented-control";

export type Tab = "waiting" | "decided";

const TABS = [
  ["waiting", "Waiting"],
  ["decided", "Decided"],
] as const;

/** The tabs a URL's ?tab= can name. */
export const TAB_IDS: readonly Tab[] = TABS.map(([id]) => id);

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
    <SegmentedControl
      label="Requests"
      dataKey="tab"
      items={TABS.map(([id, label]) => ({
        id,
        label,
        ...(counts === null ? {} : { count: counts[id] }),
      }))}
      value={tab}
      onChange={(id) => {
        if (id !== tab) onChoose(id);
      }}
    />
  );
}
