import type { ApprovalView } from "@autobots/api-client";
import { ArrowUpRight } from "lucide-react";
import Link from "next/link";

import { ApprovalFacts } from "@/components/approvals/approval-facts";
import { DecisionBar } from "@/components/approvals/decision-bar";
import { ExactRequest } from "@/components/approvals/exact-request";
import { ReviewDiffs } from "@/components/approvals/review-diffs";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import type { Decision } from "@/lib/approval-shortcut";
import { TOO_LARGE } from "@/lib/approval-text";
import { cn } from "@/lib/utils";

/**
 * The selected request: its facts, the exact request, any diffs it binds and, while it waits, the
 * decision bar. A request too long to show whole says it can't be approved (PRD-Studio AP-03).
 */
export function ApprovalDetail({
  approval,
  now,
  waiting,
  onDecide,
}: {
  approval: ApprovalView;
  now: number;
  waiting: boolean;
  onDecide: (decision: Decision) => void;
}) {
  return (
    <Card data-approval={approval.id} className="min-w-0 space-y-5 p-5 sm:p-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <CardTitle size="display" className="break-words">
          {approval.tool_id}, version {approval.tool_version}
        </CardTitle>
        <Link
          href={`/runs/${approval.run_id}`}
          className={cn(
            buttonVariants({ variant: "outline", size: "sm" }),
            "w-fit shrink-0",
          )}
        >
          Open the run
          <ArrowUpRight aria-hidden="true" />
        </Link>
      </div>
      <ApprovalFacts approval={approval} now={now} waiting={waiting} />
      <ExactRequest approval={approval} />
      {approval.review_detail === null ||
      approval.review_detail === undefined ? null : (
        <ReviewDiffs approvalId={approval.id} detail={approval.review_detail} />
      )}
      {approval.arguments_truncated ? (
        <p
          role="alert"
          className="border-destructive/35 text-destructive rounded-lg border p-3 text-sm font-medium"
        >
          {TOO_LARGE}
        </p>
      ) : null}
      {waiting ? <DecisionBar onDecide={onDecide} /> : null}
    </Card>
  );
}
