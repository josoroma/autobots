import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/field";
import { FIELD_LABEL } from "@/components/workflow-editor/field-label";
import type { NameDraft } from "@/components/workflow-editor/use-name";
import { NAME_MAX } from "@/lib/workflows/rename";

/** The workflow's name, saved without changing a version (Decision 0037 N3). */
export function NameField({ name }: { name: NameDraft }) {
  return (
    <div className="space-y-1.5">
      <label htmlFor="workflow-name" className={FIELD_LABEL}>
        Name
      </label>
      <Input
        id="workflow-name"
        maxLength={NAME_MAX}
        value={name.text}
        onChange={(event) => name.edit(event.target.value)}
      />
      <Button
        variant="outline"
        size="sm"
        disabled={name.pending}
        onClick={() => void name.save()}
      >
        Save name
      </Button>
    </div>
  );
}
