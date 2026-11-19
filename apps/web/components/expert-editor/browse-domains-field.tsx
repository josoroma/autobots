import { Field, Textarea } from "@/components/ui/field";
import type { Draft } from "@/lib/experts/draft";

/**
 * Where this Expert's browse may go while browsing's YOLO setting is on (Decision 0035 Y3). Shown
 * while the draft grants browse_goal. With none listed, a YOLO browse is refused.
 */
export function BrowseDomainsField({
  draft,
  held,
  onChange,
}: {
  draft: Draft;
  held: boolean;
  onChange: (draft: Draft) => void;
}) {
  return (
    <Field
      id="browse-domains"
      label="Browse domains"
      description="One per line. While YOLO is on, a browse may go only to these domains and their subdomains, and with none listed it is refused."
    >
      {(control) => (
        <Textarea
          {...control}
          rows={3}
          spellCheck={false}
          className="font-mono text-meta"
          value={draft.browseDomains}
          readOnly={held}
          onChange={(event) =>
            onChange({ ...draft, browseDomains: event.target.value })
          }
        />
      )}
    </Field>
  );
}
