"use client";

import {
  parseRetentionSummary,
  type RetentionSummary,
} from "@autobots/api-client";
import Link from "next/link";
import { useEffect, useState } from "react";

function kept(days: number | null, what: string): string {
  return days === null
    ? `${what} are kept until a retention window is set.`
    : `${what} are removed ${days} ${days === 1 ? "day" : "days"} after a run finishes.`;
}

// PRD-Studio SE-06: what this workspace keeps, read-only for every member. Only the owner changes it,
// on Operations, so only the owner is offered the link.
export function DataSummary() {
  const [summary, setSummary] = useState<RetentionSummary | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let live = true;
    fetch("/api/v1/retention", { cache: "no-store" })
      .then(async (reply) => {
        if (!live) return;
        if (reply.ok) setSummary(parseRetentionSummary(await reply.json()));
        else {
          await reply.text();
          setFailed(true);
        }
      })
      .catch(() => {
        if (live) setFailed(true);
      });
    return () => {
      live = false;
    };
  }, []);

  if (failed)
    return (
      <p role="alert" className="text-sm">
        The retention summary is unavailable. Sign in, and check that the local
        API is running.
      </p>
    );
  if (summary === null)
    return (
      <p role="status" className="text-muted-foreground text-sm">
        Loading the retention summary.
      </p>
    );
  return (
    <section
      aria-labelledby="retention-heading"
      data-field="retention-summary"
      className="border-border grid gap-4 border-t pt-5 md:grid-cols-[minmax(0,240px)_minmax(0,1fr)] md:gap-7"
    >
      <div className="space-y-1">
        <h2 id="retention-heading" className="text-sm font-semibold">
          Retention
        </h2>
        <p className="text-muted-foreground text-[12.5px] leading-relaxed">
          Everything here stays on this Mac. This summary is read-only.
        </p>
      </div>
      <div className="space-y-2 text-sm leading-relaxed">
        <p data-field="run-retention">
          {kept(
            summary.run_days,
            "A run's checkpoints, working files and artifact bytes",
          )}
        </p>
        <p data-field="receipt-retention">
          {kept(summary.receipt_days, "Retry keys")}
        </p>
        <p className="text-muted-foreground">
          A run&apos;s record, activity and operation receipts stay, and a run
          with an unresolved effect is never touched.
        </p>
        {summary.viewer_role === "owner" ? (
          <p>
            <Link
              href="/operations"
              data-field="operations-link"
              className="font-medium underline underline-offset-4"
            >
              Change retention on Operations
            </Link>
          </p>
        ) : (
          <p data-field="owner-only" className="text-muted-foreground">
            Only the workspace owner can change retention.
          </p>
        )}
      </div>
    </section>
  );
}
