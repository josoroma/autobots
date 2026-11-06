"use client";

import { parseRunList, type RunList as Runs } from "@autobots/api-client";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Card } from "@/components/ui/card";

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

export function RunList() {
  const [list, setList] = useState<Runs | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    fetch("/api/v1/runs", { cache: "no-store" })
      .then(async (reply) => {
        if (!active) return;
        if (reply.ok) setList(parseRunList(await reply.json()));
        else setFailed(true);
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Runs</h1>
      {failed ? (
        <p role="alert" data-state="unavailable" className="text-sm">
          Runs are unavailable. Sign in, and check that the local API is
          running.
        </p>
      ) : list === null ? (
        <p role="status" data-state="loading" className="text-sm">
          Loading runs.
        </p>
      ) : list.runs.length === 0 ? (
        <Card>
          <p data-state="empty" className="text-sm">
            This workspace has no runs yet. Start one from{" "}
            <Link href="/" className="font-medium underline">
              Home
            </Link>
            .
          </p>
        </Card>
      ) : (
        <Card className="space-y-3">
          <ul className="space-y-3 text-sm">
            {list.runs.map((run) => (
              <li key={run.id} data-run={run.id} data-status={run.status}>
                <Link
                  href={`/runs/${run.id}`}
                  className="font-medium break-words underline"
                >
                  {run.goal_summary === "" ? "Untitled run" : run.goal_summary}
                </Link>
                <p className="text-muted-foreground">
                  {STATUS_TEXT[run.status]}, started{" "}
                  {new Date(run.created_at).toISOString()}
                  {run.parent_run_id === null ? "" : ", a child run"}
                </p>
              </li>
            ))}
          </ul>
          {list.has_more ? (
            <p data-state="more" className="text-muted-foreground text-sm">
              Showing the newest {list.runs.length}. Older runs aren&apos;t
              listed here.
            </p>
          ) : null}
        </Card>
      )}
    </div>
  );
}
