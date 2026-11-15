/**
 * The chosen workflow's two reads (WBLD-11): the steps of the version shown, which needs the
 * workflow's versions to pick a default, and its recent executions, which the panel starts with the
 * list (PRD-Studio WF-03, WF-04). Each has its own state, so a failed read says why, with Retry for
 * an outage, instead of staying on Loading.
 */
import {
  previewWorkflowVersion,
  type WorkflowExecutionList,
  type WorkflowStepView,
  type WorkflowView,
} from "@autobots/api-client";

import { readOf } from "@/lib/load";
import {
  useResource,
  type Resource,
  type ResourceState,
} from "@/lib/use-resource";
import { previewVersion } from "@/lib/workflows/list";

const LOADING = { kind: "loading" } as const;

/** What shows while a read has no value: loading, or why its settled read failed. */
function waiting(read: Resource<unknown>): ResourceState<unknown> {
  return !read.pending && read.state.kind !== "ready" ? read.state : LOADING;
}

export interface WorkflowPreviewRead {
  /** The version shown, "draft", or null while nothing is published or drafted. */
  shown: string | null;
  /** The shown version's steps, or null until they're read. */
  steps: readonly WorkflowStepView[] | null;
  stepsState: ResourceState<unknown>;
  retrySteps: () => void;
  stepsPending: boolean;
  executions: WorkflowExecutionList | null;
  executionsState: ResourceState<unknown>;
  retryExecutions: () => void;
  executionsPending: boolean;
}

export function useWorkflowPreview(
  workflow: WorkflowView,
  version: string | null,
  executions: Resource<WorkflowExecutionList>,
): WorkflowPreviewRead {
  const shown = previewVersion(workflow, version);
  const preview = useResource(
    shown === null
      ? null
      : readOf(previewWorkflowVersion, workflow.id, { version: shown }),
  );
  const steps =
    preview.value !== null && String(preview.value.version) === shown
      ? preview.value.steps
      : null;
  return {
    shown,
    steps,
    stepsState: waiting(preview),
    retrySteps: preview.reload,
    stepsPending: preview.pending,
    executions: executions.value,
    executionsState: waiting(executions),
    retryExecutions: executions.reload,
    executionsPending: executions.pending,
  };
}
