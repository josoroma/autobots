import type { WorkflowValidation } from "@autobots/api-client";
import { CircleAlert, CircleCheck, ListChecks, Upload } from "lucide-react";

import { HeldNote } from "@/components/held-note";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/field";
import { FIELD_LABEL } from "@/components/workflow-editor/field-label";
import type { GraphDraft } from "@/components/workflow-editor/use-graph-draft";
import { cn } from "@/lib/utils";
import type { EditorGraph } from "@/lib/workflow-ir";

/**
 * One optional label per step (PRD-Studio WF-06). A label edit rewrites the text under the domain's
 * label rule, in lib/workflow-ir.ts (Decision 0029 F1).
 */
function StepLabels({
  graph,
  readOnly,
  onLabel,
}: {
  graph: EditorGraph;
  readOnly: boolean;
  onLabel: (nodeId: string, label: string) => void;
}) {
  return (
    <fieldset data-field="step-labels" className="min-w-0 space-y-2">
      <legend className={cn(FIELD_LABEL, "mb-1")}>Step labels</legend>
      <p className="text-muted-foreground text-meta">
        Optional. A label says what a step does, and a labelled graph is
        published at IR version 2.
      </p>
      {graph.nodes.map((node) => (
        <div
          key={node.id}
          className="flex flex-wrap items-center gap-x-3 gap-y-1"
        >
          <label
            htmlFor={`label-${node.id}`}
            className="w-40 shrink-0 font-mono text-meta break-all"
          >
            {node.id} ({node.block})
          </label>
          <Input
            id={`label-${node.id}`}
            maxLength={80}
            readOnly={readOnly}
            value={typeof node.label === "string" ? node.label : ""}
            onChange={(event) => onLabel(node.id, event.target.value)}
            className="h-8 min-w-0 flex-1"
          />
        </div>
      ))}
    </fieldset>
  );
}

/** The service's check of the text: its hash when valid, or each typed error. */
function ValidationResult({ check }: { check: WorkflowValidation | null }) {
  if (check === null) return null;
  if (check.valid) {
    return (
      <p
        role="status"
        data-validation="valid"
        className="flex items-center gap-2 text-sm"
      >
        <CircleCheck
          aria-hidden="true"
          className="text-success-text size-4 shrink-0"
        />
        <span>
          <span className="text-success-text font-medium">Valid.</span> Hash{" "}
          <span className="font-mono text-meta">
            {check.graph_hash?.slice(0, 12)}
          </span>
          .
        </span>
      </p>
    );
  }
  return (
    <div
      role="alert"
      data-validation="invalid"
      className="border-destructive/35 space-y-1.5 rounded-lg border p-3 text-sm"
    >
      <p className="text-destructive flex items-center gap-2 font-medium">
        <CircleAlert aria-hidden="true" className="size-4 shrink-0" />
        This can&apos;t be published yet:
      </p>
      <ul className="list-disc space-y-0.5 pl-10">
        {check.errors.map((error, index) => (
          <li key={`${error.code}-${index}`} data-error={error.code}>
            {error.code.replaceAll("_", " ")}
            {error.node === null ? "" : ` at ${error.node}`}
            {error.port === null ? "" : `, port ${error.port}`}
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * The Graph field, its step labels and the actions on it. Each publish action names its source:
 * the text on screen, or the saved WF-02 draft, which waits while the text differs from it
 * (PRD-Studio WF-02, WBLD-05). A stored draft the service can't read is said to be replaced by the
 * next save (R-56, SQLI-13).
 */
export function GraphEditor({
  draft,
  hasDraft,
  draftUnreadable,
}: {
  draft: GraphDraft;
  hasDraft: boolean;
  draftUnreadable: boolean;
}) {
  return (
    <>
      <div className="space-y-1.5">
        <label htmlFor="graph" className={FIELD_LABEL}>
          Graph
        </label>
        <Textarea
          id="graph"
          rows={16}
          spellCheck={false}
          value={draft.text}
          readOnly={draft.publishHeld}
          onChange={(event) => draft.edit(event.target.value)}
          className="font-mono text-meta leading-relaxed"
        />
      </div>
      {draft.graph === null ? null : (
        <StepLabels
          graph={draft.graph}
          readOnly={draft.publishHeld}
          onLabel={draft.label}
        />
      )}
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" onClick={() => void draft.validate()}>
          <ListChecks aria-hidden="true" />
          Validate
        </Button>
        <Button
          onClick={() => void draft.publish()}
          disabled={draft.publishing}
        >
          <Upload aria-hidden="true" />
          Publish what is shown
        </Button>
      </div>
      {draft.publishHeld ? <HeldNote /> : null}
      <div
        role="group"
        aria-label="Draft"
        className="flex flex-wrap items-center gap-2 border-t pt-4"
      >
        <Button variant="outline" onClick={() => void draft.save()}>
          Save draft
        </Button>
        <Button
          variant="outline"
          disabled={!hasDraft || draft.isDirty || draft.draftBusy}
          onClick={() => void draft.publishSaved()}
        >
          Publish saved draft
        </Button>
        <Button
          variant="outline"
          disabled={!hasDraft || draft.draftBusy}
          onClick={() => void draft.discard()}
        >
          Discard draft
        </Button>
        <p className="text-muted-foreground text-meta">
          Runs and routines use published versions only.
        </p>
      </div>
      {draftUnreadable ? (
        <p
          data-field="unreadable-draft-note"
          className="text-muted-foreground text-meta"
        >
          Its saved draft can&apos;t be read, so saving replaces it.
        </p>
      ) : null}
      {hasDraft && draft.isDirty ? (
        <p
          data-field="unsaved-note"
          className="text-muted-foreground text-meta"
        >
          Publish saved draft publishes what was last saved, so it waits until
          these changes are saved.
        </p>
      ) : null}
      <ValidationResult check={draft.check} />
    </>
  );
}
