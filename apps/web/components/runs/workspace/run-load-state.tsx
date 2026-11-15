import type { RunWorkspace } from "@autobots/api-client";

import { LoadState } from "@/components/ui/load-state";
import { PageHeader } from "@/components/ui/page-header";
import {
  RUN_NOT_FOUND,
  retryWords,
  shownState,
  type WorkspaceLoad,
} from "@/lib/runs/workspace-load";

// PRD-Development-Harness DH-06: loading, a refusal, a missing run, an outage being retried and a
// mismatch each read differently, and only an outage offers Retry (WRUN-02).
export function RunLoadState({
  load,
  onRetry,
}: {
  load: Exclude<WorkspaceLoad<RunWorkspace>, { kind: "ready" }>;
  onRetry: () => void;
}) {
  const state = shownState(load);
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <PageHeader title="Run" />
      {state === null ? null : (
        <LoadState
          state={state}
          what="this run"
          onRetry={onRetry}
          notFound={RUN_NOT_FOUND}
        />
      )}
      {load.kind === "retrying" ? (
        <p
          data-field="retry-in"
          data-attempt={load.attempt}
          className="text-muted-foreground text-sm"
        >
          {retryWords(load.delayMs)}
        </p>
      ) : null}
    </div>
  );
}
