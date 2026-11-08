"use client";

import {
  parseApprovalList,
  parseRunList,
  type ApprovalList,
  type RunList,
} from "@autobots/api-client";
import { CircleAlert, History } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { STATUS_TEXT } from "@/components/run-list";
import { SectionLabel } from "@/components/ui/page-header";

const RECENT = 5;
const RELATIVE = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["day", 86_400_000],
  ["hour", 3_600_000],
  ["minute", 60_000],
];

function relative(iso: string, now: number): string {
  const elapsed = Date.parse(iso) - now;
  for (const [unit, size] of UNITS) {
    if (Math.abs(elapsed) >= size) {
      return RELATIVE.format(Math.round(elapsed / size), unit);
    }
  }
  return "just now";
}

function dollars(micro: number): string {
  return `US$${(micro / 1_000_000).toFixed(2)}`;
}

type Run = RunList["runs"][number];

// HM-04: progress when the run has a plan, otherwise what it spent, marked "≈" when estimated.
function progressOrSpend(run: Run): string {
  if (run.tasks_total > 0) {
    return `${run.tasks_complete} of ${run.tasks_total} tasks`;
  }
  const estimated = run.reserved_micro_usd > 0 || run.unreported;
  const spent = dollars(run.charged_micro_usd + run.reserved_micro_usd);
  return `${estimated ? "≈ " : ""}${spent} spent`;
}

const HEAD = "mb-2 flex items-center gap-2";
const ITEM =
  "flex min-w-0 flex-wrap items-baseline gap-x-3 gap-y-0.5 border-t py-3 text-sm";
const QUIET = "text-muted-foreground border-t py-3 text-sm";

// PRD-Studio HM-04 and Decision 0022 D9: what waits for a person, then the newest runs.
export function HomeActivity() {
  const [approvals, setApprovals] = useState<ApprovalList | null>(null);
  const [waiting, setWaiting] = useState<RunList | null>(null);
  const [recent, setRecent] = useState<RunList | null>(null);
  const [failed, setFailed] = useState(false);
  const [now, setNow] = useState(0);

  useEffect(() => {
    let active = true;
    Promise.all([
      fetch("/api/v1/approvals", { cache: "no-store" }),
      fetch("/api/v1/runs?group=needs_you", { cache: "no-store" }),
      fetch("/api/v1/runs", { cache: "no-store" }),
    ])
      .then(async (replies) => {
        if (!active) return;
        if (replies.some((reply) => !reply.ok)) {
          // Read, or an unread refusal holds its connection open for as long as the page lives.
          await Promise.all(replies.map((reply) => reply.text()));
          setFailed(true);
          return;
        }
        const [approvalReply, waitingReply, recentReply] = replies;
        setApprovals(parseApprovalList(await approvalReply!.json()));
        setWaiting(parseRunList(await waitingReply!.json()));
        setRecent(parseRunList(await recentReply!.json()));
        setNow(Date.now());
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
    };
  }, []);

  if (failed) {
    return (
      <p className="text-muted-foreground mt-14 text-sm">
        What needs you and recent runs can&apos;t be read right now.
      </p>
    );
  }
  // A run waiting for approval is reached through its request, so only waiting_input is a run here.
  const replies = (waiting?.runs ?? []).filter(
    (run) => run.status === "waiting_input",
  );
  const pending = approvals?.approvals ?? [];
  const loaded = approvals !== null && waiting !== null;
  return (
    // Stacked, so Tab moves down through Needs you and then Recent runs, never back up a column.
    <div className="mt-14 grid gap-10">
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
          <p className={QUIET}>Nothing needs you right now.</p>
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
          <p className={QUIET}>No runs yet.</p>
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
                  <span data-field="state">
                    {STATUS_TEXT[run.status] ?? run.status}
                  </span>
                  <span aria-hidden="true">·</span>
                  <span data-field="progress">{progressOrSpend(run)}</span>
                  <span aria-hidden="true">·</span>
                  <time data-field="when" dateTime={run.created_at}>
                    {relative(run.created_at, now)}
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
    </div>
  );
}
