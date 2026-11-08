"use client";

import { parseRunList, type RunList as Runs } from "@autobots/api-client";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Card } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { cn } from "@/lib/utils";

const STATUS_TEXT: Record<string, string> = {
  queued: "Queued",
  running: "Running",
  waiting_input: "Waiting for input",
  waiting_approval: "Waiting for approval",
  paused: "Paused",
  verifying: "Verifying",
  cancelling: "Cancelling",
  succeeded: "Succeeded",
  failed: "Failed",
  cancelled: "Cancelled",
};

// Decision 0021 R3–R4: the dot repeats the state's words, never replaces them. What runs is live,
// what waits for a person takes the attention tone, a failure is destructive; the rest stay neutral.
type Tone = "live" | "attention" | "success" | "failure" | "idle";

function tone(status: string): Tone {
  switch (status) {
    case "running":
    case "verifying":
      return "live";
    case "waiting_input":
    case "waiting_approval":
      return "attention";
    case "succeeded":
      return "success";
    case "failed":
      return "failure";
    default:
      return "idle";
  }
}

const STATE_TEXT: Record<Tone, string> = {
  live: "text-live-text",
  attention: "text-attention",
  success: "text-foreground",
  failure: "text-destructive",
  idle: "text-foreground",
};

const STATE_DOT: Record<Tone, string> = {
  live: "bg-live-text ring-live-text/20 ring-[3px]",
  attention: "bg-attention",
  success: "bg-success-text",
  failure: "bg-destructive",
  idle: "border-muted-foreground border-[1.5px]",
};

const COLUMNS = "lg:grid-cols-[minmax(0,1fr)_11rem_12.5rem] lg:gap-x-6";

export function RunList() {
  const [list, setList] = useState<Runs | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    fetch("/api/v1/runs", { cache: "no-store" })
      .then(async (reply) => {
        if (!active) return;
        if (reply.ok) setList(parseRunList(await reply.json()));
        else {
          await reply.text();
          setFailed(true);
        }
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="max-w-5xl space-y-6">
      <PageHeader title="Runs" />
      {failed ? (
        <p
          role="alert"
          data-state="unavailable"
          className="border-destructive/35 text-destructive rounded-lg border p-4 text-sm"
        >
          Runs are unavailable. Sign in, and check that the local API is
          running.
        </p>
      ) : list === null ? (
        <p
          role="status"
          data-state="loading"
          className="text-muted-foreground text-sm"
        >
          Loading runs.
        </p>
      ) : list.runs.length === 0 ? (
        <Card className="border-dashed">
          <p data-state="empty" className="text-sm">
            This workspace has no runs yet. Start one from{" "}
            <Link href="/" className="font-medium underline">
              Home
            </Link>
            .
          </p>
        </Card>
      ) : (
        <div>
          {/* Column names for sighted readers; each row says its own state and start time. */}
          <div
            aria-hidden="true"
            className={cn(
              COLUMNS,
              "text-muted-foreground hidden border-b px-3 pb-2.5 text-[12.5px] font-medium lg:grid",
            )}
          >
            <span>Goal</span>
            <span>State</span>
            <span className="text-right">Started</span>
          </div>
          <ul className="divide-border divide-y border-b text-[13.5px] max-lg:border-t">
            {list.runs.map((run) => (
              <li
                key={run.id}
                data-run={run.id}
                data-status={run.status}
                className={cn(
                  COLUMNS,
                  "grid gap-x-6 gap-y-1.5 px-3 py-3 lg:min-h-[52px] lg:items-center lg:py-2",
                )}
              >
                <div className="min-w-0">
                  <Link
                    href={`/runs/${run.id}`}
                    className="text-foreground font-medium break-words underline-offset-4 hover:underline"
                  >
                    {run.goal_summary === ""
                      ? "Untitled run"
                      : run.goal_summary}
                  </Link>
                  {run.parent_run_id === null ? null : (
                    <span className="text-muted-foreground mt-0.5 block text-xs">
                      A child run
                    </span>
                  )}
                </div>
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 lg:contents">
                  <span
                    className={cn(
                      "inline-flex items-center gap-2 text-[13px]",
                      STATE_TEXT[tone(run.status)],
                    )}
                  >
                    <span
                      aria-hidden="true"
                      className={cn(
                        "size-[7px] shrink-0 rounded-full",
                        STATE_DOT[tone(run.status)],
                      )}
                    />
                    {STATUS_TEXT[run.status]}
                  </span>
                  <span className="text-muted-foreground tabular-nums lg:text-right">
                    <span className="lg:sr-only">Started </span>
                    {new Date(run.created_at).toISOString()}
                  </span>
                </div>
              </li>
            ))}
          </ul>
          {list.has_more ? (
            <p
              data-state="more"
              className="text-muted-foreground mt-4 text-[12.5px]"
            >
              Showing the newest {list.runs.length}. Older runs aren&apos;t
              listed here.
            </p>
          ) : null}
        </div>
      )}
    </div>
  );
}
