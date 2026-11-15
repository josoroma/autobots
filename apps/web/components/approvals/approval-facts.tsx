import type { ApprovalView } from "@autobots/api-client";
import type { ReactNode } from "react";

import {
  decidedText,
  NOT_RECORDED,
  policyText,
  requesterText,
  scopeText,
} from "@/lib/approval-text";
import { untilDeadline } from "@/lib/format";
import { cn } from "@/lib/utils";

// One labelled fact. The colon is for assistive technology and copied text; sighted readers see the label
// above the value.
function Fact({
  label,
  colon = true,
  className,
  children,
  ...props
}: {
  label: string;
  colon?: boolean;
  className?: string;
  children: ReactNode;
} & Record<`data-${string}`, string>) {
  return (
    <div
      className={cn(
        "border-b px-3.5 py-3 last:border-b-0 sm:odd:border-r",
        className,
      )}
      {...props}
    >
      <dt className="text-muted-foreground mb-0.5 text-xs">
        {label}
        {colon ? <span className="sr-only">:</span> : null}
      </dt>{" "}
      <dd className="break-words">{children}</dd>
    </div>
  );
}

/**
 * What the request is, as stored with it: who asked, why, its run and task, its scope and policy
 * (Decision 0015), and its expiry, read against a clock that keeps moving (Decision 0028 E5).
 */
export function ApprovalFacts({
  approval,
  now,
  waiting,
}: {
  approval: ApprovalView;
  now: number;
  waiting: boolean;
}) {
  return (
    <dl className="grid overflow-hidden rounded-lg border text-ui sm:grid-cols-2">
      <Fact data-approval-requester="true" label="Requested by">
        {requesterText(approval)}
      </Fact>
      <Fact data-approval-reason="true" label="Why it's asking">
        {approval.policy_reason ?? NOT_RECORDED}
      </Fact>
      <Fact data-approval-run="true" label="Run">
        {approval.run_goal ?? "not recorded."}
      </Fact>
      <Fact data-approval-task="true" label="For task">
        {approval.task_title ?? "not recorded for this call."}
      </Fact>
      <Fact data-approval-scope="true" label="Scope when asked">
        {scopeText(approval)}
      </Fact>
      <Fact data-approval-policy="true" label="Policy version">
        {policyText(approval)}
      </Fact>
      <Fact label="Expires" colon={false}>
        <span className={waiting ? "text-attention" : undefined}>
          {new Date(approval.expires_at).toLocaleString()}.
        </span>{" "}
        <span className="text-muted-foreground">
          ({untilDeadline(approval.expires_at, now)})
        </span>
      </Fact>
      {waiting ? (
        <Fact label="Status">Waiting for a decision.</Fact>
      ) : (
        <Fact data-approval-decided="true" label="Decided">
          {decidedText(approval)}
        </Fact>
      )}
    </dl>
  );
}
