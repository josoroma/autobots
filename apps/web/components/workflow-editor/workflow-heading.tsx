import type { WorkflowView } from "@autobots/api-client";

import { Badge } from "@/components/ui/badge";

/**
 * The workflow's name, its published version, whether a WF-02 draft is saved, and whether the
 * Graph field holds changes that aren't saved (PRD-Studio WF-02, WBLD-05).
 */
export function WorkflowHeading({
  workflow,
  unsaved,
}: {
  workflow: WorkflowView;
  unsaved: boolean;
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
      <h2
        id="graph-heading"
        className="font-serif text-[22px] leading-tight font-normal tracking-tight wrap-anywhere"
      >
        {workflow.name}
      </h2>
      {workflow.latest_version === 0 ? (
        <Badge variant="attention" dot>
          Not published
        </Badge>
      ) : (
        <Badge variant="outline">Version {workflow.latest_version}</Badge>
      )}
      {workflow.draft === null ? null : (
        <Badge variant="attention" dot data-field="draft-badge">
          Draft saved
        </Badge>
      )}
      {unsaved ? (
        <Badge variant="muted" data-field="unsaved-badge">
          Unsaved changes
        </Badge>
      ) : null}
    </div>
  );
}
