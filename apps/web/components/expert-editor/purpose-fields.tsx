import { Input, Textarea } from "@/components/ui/field";
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
      <div className="space-y-1.5">
        <label htmlFor="purpose" className="text-sm font-medium">
          Purpose
        </label>
        <Input
          id="purpose"
          value={draft.purpose}
          readOnly={held}
          onChange={(event) =>
            onChange({ ...draft, purpose: event.target.value })
          }
        />
      </div>
      <div className="space-y-1.5">
        <label htmlFor="instructions" className="text-sm font-medium">
          Instructions
        </label>
        <Textarea
          id="instructions"
          rows={5}
          value={draft.instructions}
          readOnly={held}
          onChange={(event) =>
            onChange({ ...draft, instructions: event.target.value })
          }
        />
      </div>
    </div>
  );
}
