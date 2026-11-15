"use client";

import type { ApprovalView } from "@autobots/api-client";
import { useState } from "react";

import { ApprovalDetail } from "@/components/approvals/approval-detail";
import { ApprovalList } from "@/components/approvals/approval-list";
import { ApprovalTabs, type Tab } from "@/components/approvals/approval-tabs";
import { useApprovalDecision } from "@/components/approvals/use-approval-decision";
import { useApprovalList } from "@/components/approvals/use-approval-list";
import { useApprovalShortcuts } from "@/components/approvals/use-approval-shortcuts";
import { Card, INNER_BOX } from "@/components/ui/card";
import { LoadState } from "@/components/ui/load-state";
import { cn } from "@/lib/utils";

// The chosen request while it's listed, or else the first, so a reload never selects a missing one.
function selectedIn(
  approvals: readonly ApprovalView[],
  chosen: string | null,
): string | null {
  return approvals.some((item) => item.id === chosen)
    ? chosen
    : (approvals[0]?.id ?? null);
}

// PRD-Studio AP-01 to AP-04: Waiting and Decided with counts, the list beside the selected request,
// J and K to move, and ⌘↵ or ⌘⌫ pressed twice within 2 s to decide. Every decision is the
// service's; this screen reads the list, asks for decisions and shows what they did.
export function ApprovalsPanel({
  initial = null,
}: {
  // HM-04: Home's Review link opens with its request selected, when it's still waiting.
  initial?: string | null;
}) {
  const [tab, setTab] = useState<Tab>("waiting");
  const [chosen, setChosen] = useState<string | null>(initial);
  const read = useApprovalList(tab);
  const decision = useApprovalDecision(read.reload);
  const approvals = read.list?.approvals ?? [];
  const selected = selectedIn(approvals, chosen);
  const current = approvals.find((item) => item.id === selected) ?? null;
  const waiting = tab === "waiting";
  const shortcuts = useApprovalShortcuts({
    approvals,
    selected,
    current,
    waiting,
    select: setChosen,
    decide: (approval, choice) => void decision.decide(approval, choice),
  });

  return (
    <div className="space-y-4">
      <ApprovalTabs
        tab={tab}
        counts={read.counts}
        onChoose={(next) => {
          setTab(next);
          decision.clearMessage();
          shortcuts.disarm();
        }}
      />
      {decision.message === null ? null : (
        <p
          role="status"
          data-message="decision"
          className={cn(INNER_BOX, "text-sm")}
        >
          {decision.message}
        </p>
      )}
      <p
        aria-live="polite"
        data-message="shortcut"
        className="text-muted-foreground min-h-5 text-[12.5px]"
      >
        {shortcuts.announcement}
      </p>
      {read.list === null ? (
        <LoadState
          state={read.state}
          what="approvals"
          onRetry={read.reload}
          pending={read.pending}
        />
      ) : approvals.length === 0 ? (
        <Card className="border-dashed">
          <p className="text-sm">
            {waiting
              ? "Nothing is waiting for a decision."
              : "Nothing has been decided yet."}
          </p>
        </Card>
      ) : (
        <div className="grid gap-5 lg:grid-cols-[minmax(0,20rem)_minmax(0,1fr)]">
          <ApprovalList
            approvals={approvals}
            selected={selected}
            waiting={waiting}
            now={read.now}
            onSelect={(id) => {
              setChosen(id);
              shortcuts.disarm();
            }}
          />
          {current === null ? null : (
            <ApprovalDetail
              key={current.id}
              approval={current}
              now={read.now}
              waiting={waiting}
              onDecide={(choice) => void decision.decide(current, choice)}
            />
          )}
        </div>
      )}
    </div>
  );
}
