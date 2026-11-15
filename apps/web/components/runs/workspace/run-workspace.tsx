"use client";

import { useRouter } from "next/navigation";
import { useCallback } from "react";

import { ArtifactsSection } from "@/components/runs/workspace/artifacts-section";
import { BudgetsSection } from "@/components/runs/workspace/budgets-section";
import { ExpertSection } from "@/components/runs/workspace/expert-section";
import { GoalSection } from "@/components/runs/workspace/goal-section";
import { ModelsSection } from "@/components/runs/workspace/models-section";
import { PlanSection } from "@/components/runs/workspace/plan-section";
import {
  AssignmentsSection,
  ParentRunLink,
} from "@/components/runs/workspace/related-runs";
import { ResultSection } from "@/components/runs/workspace/result-section";
import { usePublishRunStatus } from "@/components/runs/workspace/run-heading";
import { RunLoadState } from "@/components/runs/workspace/run-load-state";
import { StatusSection } from "@/components/runs/workspace/status-section";
import { TimelineSection } from "@/components/runs/workspace/timeline-section";
import { UnknownOutcomesSection } from "@/components/runs/workspace/unknown-outcomes-section";
import { UsageSection } from "@/components/runs/workspace/usage-section";
import { usePublishedResult } from "@/components/runs/workspace/use-published-result";
import { useRunEvents } from "@/components/runs/workspace/use-run-events";
import { useRunWorkspace } from "@/components/runs/workspace/use-run-workspace";
import { VerificationSection } from "@/components/runs/workspace/verification-section";
import { ToolsUsed } from "@/components/runs/tool-uses/tools-used";
import { toWorkspaceView } from "@/lib/runs/workspace-view";

// The run page's body (PRD-Studio RN-05): one region per component, so a story changes the region it
// is about. Every region reads the same snapshot, and the stream lives in `useRunWorkspace`
// (WRUN-01). Live text changes only the Result region: the others are memoized, and their props keep
// their identity until the snapshot or the stored events change. The page owns the title and width,
// and its header shows the status this reports (XWEB-19).
export function RunWorkspaceView({ runId }: { runId: string }) {
  const { load, events, gap, live, refresh, retry } = useRunWorkspace(runId);
  const router = useRouter();
  // A command, a charge or a resolved effect changes the run: the snapshot is read again, and the
  // page is rendered again on the server, so its server-read parts and a page Back returns to follow
  // (XWEB-14). Stable, so the memoized regions keep their props.
  const changed = useCallback(() => {
    refresh();
    router.refresh();
  }, [refresh, router]);
  const { timeline, toolEvents, published } = useRunEvents(events);
  const result = usePublishedResult(published);
  usePublishRunStatus(load.kind === "ready" ? load.snapshot.run.status : null);
  if (load.kind !== "ready")
    return <RunLoadState load={load} onRetry={retry} />;
  const { snapshot, connection } = load;
  const view = toWorkspaceView(snapshot);
  return (
    <div className="grid gap-x-10 xl:grid-cols-[minmax(0,1fr)_18rem]">
      <div className="min-w-0 space-y-6">
        <StatusSection
          runId={runId}
          snapshot={snapshot}
          connection={connection}
          onRetry={retry}
          onChanged={changed}
        />
        <VerificationSection verification={snapshot.verification} />
        <ResultSection result={result} live={live} />
        <GoalSection
          objective={snapshot.objective}
          criteria={snapshot.criteria}
        />
        <PlanSection plan={snapshot.plan} />
        <ToolsUsed runId={runId} version={toolEvents} />
        <UnknownOutcomesSection
          runId={runId}
          operations={snapshot.unknown_operations}
          onResolved={changed}
        />
        <ParentRunLink parentRunId={snapshot.run.parent_run_id} />
        <AssignmentsSection assignments={snapshot.assignments} />
        <ArtifactsSection artifacts={snapshot.artifacts} />
        <TimelineSection events={timeline} gap={gap} />
      </div>
      <div className="min-w-0 space-y-6 pt-6 xl:pt-0">
        <ExpertSection expert={snapshot.expert} />
        <ModelsSection
          roleMap={snapshot.role_map}
          summarizerDiffers={view.summarizerDiffers}
        />
        <BudgetsSection
          snapshot={snapshot}
          contextThousands={view.contextThousands}
        />
        <UsageSection snapshot={snapshot} unsettled={view.unsettled} />
      </div>
    </div>
  );
}
