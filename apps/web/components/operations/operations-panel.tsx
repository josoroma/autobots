"use client";

import { ConditionGrid } from "@/components/operations/condition-grid";
import {
  DelayedSchedules,
  RestoreHistory,
} from "@/components/operations/history-lists";
import { JobsChart } from "@/components/operations/jobs-chart";
import { OperationFacts } from "@/components/operations/operation-facts";
import { RetentionForm } from "@/components/operations/retention-form";
import { RouteQualifications } from "@/components/operations/route-qualifications";
import { useLocalStatus } from "@/components/operations/use-local-status";
import { VerdictBanner } from "@/components/operations/verdict-banner";
import { LoadState } from "@/components/ui/load-state";
import { OWNER_ONLY } from "@/lib/operations-text";

// PRD-Studio OP-01 to OP-04: the verdict and its checks, the facts, the jobs chart, the history,
// each route's qualification and retention, from one read of the local status.
export function OperationsPanel() {
  const read = useLocalStatus();
  if (read.denied) return <p role="alert">{OWNER_ONLY}</p>;
  const status = read.status;
  if (status === null) {
    return (
      <LoadState
        state={read.state}
        what="operations"
        onRetry={read.reload}
        pending={read.pending}
      />
    );
  }
  const routes = status.route_qualifications;
  return (
    <div className="space-y-5">
      <VerdictBanner status={status} onCheckAgain={read.reload} />
      <ConditionGrid status={status} />
      <OperationFacts status={status} />
      {status.queue === null ? null : <JobsChart />}
      <div className="grid gap-5 lg:grid-cols-2">
        <DelayedSchedules occurrences={status.delayed_schedules} />
        <RestoreHistory restores={status.restores} />
      </div>
      {routes.length === 0 && status.retention === null ? null : (
        <div className="grid gap-5 lg:grid-cols-2">
          {routes.length === 0 ? null : <RouteQualifications routes={routes} />}
          {status.retention === null ? null : (
            <RetentionForm
              retention={status.retention}
              read={read.settled}
              onSaved={read.reload}
            />
          )}
        </div>
      )}
    </div>
  );
}
