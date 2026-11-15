"use client";

import {
  createWorkflow,
  listWorkflowExecutions,
  listWorkflows,
} from "@autobots/api-client";
import { useState } from "react";

import { CreateByName } from "@/components/list-detail/create-by-name";
import { ListSection } from "@/components/list-detail/list-section";
import { useCreateByName } from "@/components/list-detail/use-create-by-name";
import { LoadState } from "@/components/ui/load-state";
import { useWorkflowFilter } from "@/components/workflows/use-workflow-filter";
import { WorkflowPreview } from "@/components/workflows/workflow-preview";
import { WorkflowTable } from "@/components/workflows/workflow-table";
import { WorkflowToolbar } from "@/components/workflows/workflow-toolbar";
import { filterList, tabCounts } from "@/lib/list-filter";
import { readOf } from "@/lib/load";
import { useResource } from "@/lib/use-resource";
import { inWorkflowTab, WORKFLOW_TAB_IDS } from "@/lib/workflows/list";

const CREATE_REFUSALS: Readonly<Record<string, string>> = {
  owner_required: "Only the workspace owner can create a workflow.",
  workflow_name_taken: "That name is already used.",
};

/**
 * PRD-Studio WF-01, WF-03 and WF-04: tabs, search, the rows' facts, and the selected workflow's
 * preview and recent executions. The preview sits under the list, so Tab never climbs.
 */
export function WorkflowsPanel() {
  const filter = useWorkflowFilter();
  const read = useResource(readOf(listWorkflows));
  // The chosen workflow's executions need only its ID, so a linked preview reads them with the list.
  const executions = useResource(
    filter.selected === null
      ? null
      : readOf(listWorkflowExecutions, filter.selected),
  );
  const [message, say] = useState<string | null>(null);
  const create = useCreateByName(
    {
      operation: createWorkflow,
      body: (name) => ({ name }),
      hrefFor: (workflow) => `/workflows/${workflow.id}`,
      refusals: CREATE_REFUSALS,
    },
    say,
  );
  const workflows = read.value?.workflows ?? null;
  if (workflows === null) {
    return (
      <LoadState
        state={read.state}
        what="workflows"
        onRetry={read.reload}
        pending={read.pending}
      />
    );
  }
  // When the list was read, so each relative time is measured from then, not during render.
  const now = read.settledAt ?? 0;
  const shown = filterList(
    workflows,
    filter,
    inWorkflowTab,
    (item) => item.name,
  );
  const chosen = workflows.find((item) => item.id === filter.selected) ?? null;
  return (
    <>
      <ListSection
        heading="Your workflows"
        className="space-y-3"
        toolbar={
          <WorkflowToolbar
            filter={filter}
            counts={tabCounts(workflows, WORKFLOW_TAB_IDS, inWorkflowTab)}
          />
        }
        total={workflows.length}
        shown={shown.length}
        empty="No workflows yet."
        noMatch="No workflow matches."
      >
        <WorkflowTable
          rows={shown}
          selected={filter.selected}
          previewHref={(id) => filter.href({ workflow: id, version: null })}
          now={now}
        />
      </ListSection>
      {chosen === null ? null : (
        <WorkflowPreview
          key={chosen.id}
          workflow={chosen}
          version={filter.version}
          executions={executions}
          onChooseVersion={(version) => filter.replace({ version })}
          now={now}
        />
      )}
      <CreateByName
        heading="New workflow"
        inputId="workflow-name"
        create={create}
        message={message}
      />
    </>
  );
}
