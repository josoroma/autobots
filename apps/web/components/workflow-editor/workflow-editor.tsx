"use client";

import { getWorkflow, type WorkflowView } from "@autobots/api-client";
import { useState } from "react";

import { Card } from "@/components/ui/card";
import { LoadState } from "@/components/ui/load-state";
import { BlockCatalogTable } from "@/components/workflow-editor/block-catalog-table";
import { DescriptionField } from "@/components/workflow-editor/description-field";
import { GraphEditor } from "@/components/workflow-editor/graph-editor";
import { RunVersionCard } from "@/components/workflow-editor/run-version-card";
import { useDescription } from "@/components/workflow-editor/use-description";
import { useGraphDraft } from "@/components/workflow-editor/use-graph-draft";
import { WorkflowHeading } from "@/components/workflow-editor/workflow-heading";
import { readOf } from "@/lib/load";
import { useResource } from "@/lib/use-resource";

/**
 * The editor's cards around one workflow view. The heading, description and graph share one message
 * line, which the suites read as `data-message="editor"`; a run says its outcome in its own card.
 */
function EditorLayout({
  workflow,
  onSaved,
}: {
  workflow: WorkflowView;
  onSaved: (view: WorkflowView) => void;
}) {
  const [message, say] = useState<string | null>(null);
  const draft = useGraphDraft(workflow, onSaved, say);
  const description = useDescription(workflow, onSaved, say);
  return (
    <div className="grid items-start gap-6 @4xl:grid-cols-[minmax(0,1fr)_320px]">
      <Card
        aria-labelledby="graph-heading"
        className="space-y-4 p-6 @4xl:col-start-1 @4xl:row-start-1"
      >
        <WorkflowHeading workflow={workflow} unsaved={draft.isDirty} />
        <DescriptionField description={description} />
        <GraphEditor
          draft={draft}
          hasDraft={workflow.draft !== null}
          draftUnreadable={workflow.draft_unreadable}
        />
        {message === null ? null : (
          <p role="status" data-message="editor" className="text-sm">
            {message}
          </p>
        )}
      </Card>
      <RunVersionCard
        workflow={workflow}
        className="@4xl:col-start-1 @4xl:row-start-2"
      />
      <BlockCatalogTable className="@4xl:col-start-2 @4xl:row-span-2 @4xl:row-start-1" />
    </div>
  );
}

/**
 * One workflow's editor (PRD-Studio WF-02, WF-05, WF-06). The workflow is read once, with its own
 * loading and unavailable states; after a write, the view the service returned is shown instead.
 */
export function WorkflowEditor({ workflowId }: { workflowId: string }) {
  const read = useResource(readOf(getWorkflow, workflowId));
  const [written, setWritten] = useState<{
    workflowId: string;
    view: WorkflowView;
  } | null>(null);
  const workflow =
    written?.workflowId === workflowId ? written.view : read.value;
  if (workflow === null) {
    return (
      <LoadState
        state={read.state}
        what="this workflow"
        notFound="That workflow is not available."
        onRetry={read.reload}
        pending={read.pending}
      />
    );
  }
  return (
    <EditorLayout
      key={workflowId}
      workflow={workflow}
      onSaved={(view) => setWritten({ workflowId, view })}
    />
  );
}
