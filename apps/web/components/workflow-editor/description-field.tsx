import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/field";
import { FIELD_LABEL } from "@/components/workflow-editor/field-label";
import type { DescriptionDraft } from "@/components/workflow-editor/use-description";

/** The workflow's optional description, saved without changing a version (PRD-Studio WF-06). */
export function DescriptionField({
  description,
}: {
  description: DescriptionDraft;
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor="workflow-description" className={FIELD_LABEL}>
        Description
      </label>
      <Textarea
        id="workflow-description"
        rows={2}
        maxLength={500}
        value={description.text}
        placeholder="What this workflow does"
        onChange={(event) => description.edit(event.target.value)}
      />
      <Button
        variant="outline"
        size="sm"
        disabled={description.pending}
        onClick={() => void description.save()}
      >
        Save description
      </Button>
    </div>
  );
}
