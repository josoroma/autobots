"use client";

import {
  listApprovals,
  listRuns,
  type ApprovalList,
  type RunList,
} from "@autobots/api-client";
import { CircleAlert, History } from "lucide-react";
import Link from "next/link";

import { LoadEmpty, LoadState } from "@/components/ui/load-state";
import { SectionLabel } from "@/components/ui/page-header";
import { spendOf } from "@/lib/budget";
import { formatRelative, formatUsd } from "@/lib/format";
import { readOf, worstFailure } from "@/lib/load";
import { RUN_STATUS_LABEL } from "@/lib/runs/status";
import { useResource } from "@/lib/use-resource";

const RECENT = 5;

type Run = RunList["runs"][number];

// HM-04: progress when the run has a plan, otherwise what it spent, marked "≈" when estimated.
function progressOrSpend(run: Run): string {
  if (run.tasks_total > 0) {
    return `${run.tasks_complete} of ${run.tasks_total} tasks`;
  }
  const { micro, estimated } = spendOf(
    run.charged_micro_usd,
    run.reserved_micro_usd,
    run.unreported,
  );
  return `${estimated ? "≈ " : ""}${formatUsd(micro)} spent`;
}

const HEAD = "mb-2 flex items-center gap-2";
const ITEM =
  "flex min-w-0 flex-wrap items-baseline gap-x-3 gap-y-0.5 border-t py-3 text-sm";
const QUIET = "text-muted-foreground border-t py-3 text-sm";

// PRD-Studio HM-04 and Decision 0022 D9: what waits for a person, then the newest runs.
export function HomeActivity() {
  const approvalRead = useResource(readOf(listApprovals));
  const waitingRead = useResource(readOf(listRuns, { group: "needs_you" }));
  const recentRead = useResource(readOf(listRuns));
  const reads = [approvalRead, waitingRead, recentRead];
  // One message for the three reads, since either section alone would mislead.
  const failure = worstFailure(reads.map((read) => read.state));
  if (failure !== null) {
    return (
      <LoadState
        state={failure}
        what="what needs you and recent runs"
        onRetry={() => reads.forEach((read) => read.reload())}
        pending={reads.some((read) => read.pending)}
        className="mt-14"
      />
    );
  }
  return (
    // Stacked, so Tab moves down through Needs you and then Recent runs, never back up a column.
    <div className="mt-14 grid gap-10">
      <NeedsYou
        approvals={
          approvalRead.state.kind === "ready" ? approvalRead.state.value : null
        }
        waiting={
          waitingRead.state.kind === "ready" ? waitingRead.state.value : null
        }
      />
      <RecentRuns
        recent={
          recentRead.state.kind === "ready" ? recentRead.state.value : null
        }
        now={recentRead.settledAt ?? 0}
      />
    </div>
  );
}

function NeedsYou({
  approvals,
  waiting,
}: {
  approvals: ApprovalList | null;
  waiting: RunList | null;
}) {
  // A run waiting for approval is reached through its request, so only waiting_input is a run here.
  const replies = (waiting?.runs ?? []).filter(
    (run) => run.status === "waiting_input",
  );
  const pending = approvals?.approvals ?? [];
  const loaded = approvals !== null && waiting !== null;
  return (
    <section
      aria-labelledby="needs-you-heading"
      data-field="needs-you"
      className="flex min-w-0 flex-col"
    >
      <div className={HEAD}>
        <CircleAlert
          aria-hidden="true"
          className="text-muted-foreground size-3.5 shrink-0"
        />
        <SectionLabel id="needs-you-heading" className="text-[12.5px]">
          Needs you
        </SectionLabel>
      </div>
      {!loaded ? (
        <p className={QUIET}>Loading.</p>
      ) : pending.length === 0 && replies.length === 0 ? (
        <LoadEmpty className={QUIET}>Nothing needs you right now.</LoadEmpty>
      ) : (
        <ul>
          {pending.map((approval) => (
            <li
              key={approval.id}
              data-needs-approval={approval.id}
              className={ITEM}
            >
              <span className="min-w-0 flex-1 wrap-anywhere">
                <span className="text-muted-foreground">Approve </span>
                <code className="text-[12.5px]">{approval.tool_id}</code>
                {approval.run_goal === null ? null : (
                  <span className="text-muted-foreground">
                    {" "}
                    for {approval.run_goal}
                  </span>
                )}
              </span>
              <Link
                href={`/approvals?approval=${encodeURIComponent(approval.id)}`}
                className="font-medium underline underline-offset-4"
              >
                Review
              </Link>
            </li>
          ))}
          {replies.map((run) => (
            <li key={run.id} data-needs-reply={run.id} className={ITEM}>
              <span className="min-w-0 flex-1 wrap-anywhere">
                <span className="text-muted-foreground">
                  Waiting for input:{" "}
                </span>
                {run.goal_summary}
              </span>
              <Link
                href={`/runs/${encodeURIComponent(run.id)}`}
                className="font-medium underline underline-offset-4"
              >
                Reply on the run
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

// Relative times are measured from `now`, when the recent runs were read.
function RecentRuns({ recent, now }: { recent: RunList | null; now: number }) {
  return (
    <section
      aria-labelledby="recent-heading"
      data-field="recent-runs"
      className="flex min-w-0 flex-col"
    >
      <div className={HEAD}>
        <History
          aria-hidden="true"
          className="text-muted-foreground size-3.5 shrink-0"
        />
        <SectionLabel id="recent-heading" className="text-[12.5px]">
          Recent runs
        </SectionLabel>
      </div>
      {recent === null ? (
        <p className={QUIET}>Loading.</p>
      ) : recent.runs.length === 0 ? (
        <LoadEmpty className={QUIET}>No runs yet.</LoadEmpty>
      ) : (
        <ul>
          {recent.runs.slice(0, RECENT).map((run) => (
            <li key={run.id} data-recent-run={run.id} className={ITEM}>
              <Link
                href={`/runs/${encodeURIComponent(run.id)}`}
                className="min-w-0 flex-1 font-medium wrap-anywhere underline-offset-4 hover:underline"
              >
                {run.goal_summary}
              </Link>
              <span className="text-muted-foreground flex flex-wrap gap-x-2 text-[12.5px] tabular-nums">
                <span data-field="state">{RUN_STATUS_LABEL[run.status]}</span>
                <span aria-hidden="true">·</span>
                <span data-field="progress">{progressOrSpend(run)}</span>
                <span aria-hidden="true">·</span>
                <time data-field="when" dateTime={run.created_at}>
                  {formatRelative(run.created_at, now)}
                </time>
              </span>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-auto pt-2">
        <Link
          href="/runs"
          className="text-sm font-medium underline underline-offset-4"
        >
          Open the run list
        </Link>
      </div>
    </section>
  );
}
