import type { RunWorkspace } from "@autobots/api-client";
import Link from "next/link";
import { memo } from "react";

import { ContinueRun } from "@/components/runs/continue/continue-run";
import { RunControls } from "@/components/runs/controls/run-controls";
import { Section } from "@/components/runs/workspace/section";
import { Button } from "@/components/ui/button";
import { RUN_STATUS_SENTENCE, stopReasonText } from "@/lib/runs/status";
import type { Connection } from "@/lib/runs/workspace-load";
import { connectionText, toWorkspaceView } from "@/lib/runs/workspace-view";
import { cn } from "@/lib/utils";

/** The run's status and reason, the stream's state, and what a person can do now. */
export const StatusSection = memo(function StatusSection({
  runId,
  snapshot,
  connection,
  onRetry,
  onChanged,
}: {
  runId: string;
  snapshot: RunWorkspace;
  connection: Connection;
  onRetry: () => void;
  onChanged: () => void;
}) {
  const view = toWorkspaceView(snapshot);
  return (
    <Section id="status-heading" title="Status">
      <p
        role="status"
        data-run-status={snapshot.run.status}
        className="text-[15px] leading-relaxed"
      >
        {RUN_STATUS_SENTENCE[snapshot.run.status]}
        {snapshot.stop_reason === null ? null : (
          <span data-stop-reason={snapshot.stop_reason}>
            {" "}
            Reason: {stopReasonText(snapshot.stop_reason)}.
          </span>
        )}
      </p>
      {view.awaitsApproval ? (
        <p className="text-sm">
          <Link
            href="/approvals"
            className="text-attention font-medium underline underline-offset-4"
          >
            Review it in Approvals
          </Link>
        </p>
      ) : null}
      <ConnectionLine connection={connection} onRetry={onRetry} />
      {snapshot.can_continue ? <ContinueRun runId={runId} /> : null}
      <RunControls
        runId={runId}
        commands={snapshot.allowed_commands}
        version={snapshot.run.version}
        openCalls={view.openCalls}
        onChanged={onChanged}
      />
    </Section>
  );
});

// The stream's state under the status. While reconnecting, Retry tries now rather than after the wait.
function ConnectionLine({
  connection,
  onRetry,
}: {
  connection: Connection;
  onRetry: () => void;
}) {
  return (
    <>
      <p
        data-connection={connection}
        className="text-muted-foreground flex items-center gap-2 text-xs"
      >
        <span
          aria-hidden="true"
          className={cn(
            "size-1.5 shrink-0 rounded-full",
            connection === "live" ? "bg-live-text" : "bg-muted-foreground",
          )}
        />
        {connectionText(connection)}
      </p>
      {connection === "reconnecting" ? (
        <Button variant="outline" size="sm" onClick={onRetry}>
          Retry
        </Button>
      ) : null}
    </>
  );
}
