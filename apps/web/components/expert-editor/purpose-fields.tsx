import { Field, Input, Textarea } from "@/components/ui/field";
import type { Draft } from "@/lib/experts/draft";

/** The Expert's purpose and instructions, which stay as sent while a save is held. */
export function PurposeFields({
  draft,
  held,
  onChange,
}: {
  draft: Draft;
  held: boolean;
  onChange: (draft: Draft) => void;
}) {
  return (
    <div className="space-y-4">
      <Field id="purpose" label="Purpose">
        {(control) => (
          <Input
            {...control}
            value={draft.purpose}
            readOnly={held}
            onChange={(event) =>
              onChange({ ...draft, purpose: event.target.value })
            }
          />
        )}
      </Field>
      <Field id="instructions" label="Instructions">
        {(control) => (
          <Textarea
            {...control}
            rows={5}
            value={draft.instructions}
            readOnly={held}
            onChange={(event) =>
              onChange({ ...draft, instructions: event.target.value })
            }
          />
        )}
      </Field>
    </div>
  );
}
