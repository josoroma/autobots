"use client";

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
import { RunHeader } from "@/components/runs/workspace/run-header";
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

// The run page (PRD-Studio RN-05): one region per component, so a story changes the region it is
// about. Every region reads the same snapshot, and the stream lives in `useRunWorkspace` (WRUN-01).
// Live text changes only the Result region: the others are memoized, and their props keep their
// identity until the snapshot or the stored events change.
export function RunWorkspaceView({ runId }: { runId: string }) {
  const { load, events, gap, live, refresh, retry } = useRunWorkspace(runId);
  const { timeline, toolEvents, published } = useRunEvents(events);
  const result = usePublishedResult(published);
  if (load.kind !== "ready")
    return <RunLoadState load={load} onRetry={retry} />;
  const { snapshot, connection } = load;
  const view = toWorkspaceView(snapshot);
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <RunHeader runId={runId} status={snapshot.run.status} />
      <div className="grid gap-x-10 xl:grid-cols-[minmax(0,1fr)_18rem]">
        <div className="min-w-0 space-y-6">
          <StatusSection
            runId={runId}
            snapshot={snapshot}
            connection={connection}
            onRetry={retry}
            onChanged={refresh}
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
            onResolved={refresh}
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
    </div>
  );
}
