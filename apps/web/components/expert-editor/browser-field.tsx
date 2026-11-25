import { Field, Select } from "@/components/ui/field";
import { BROWSERS, browserChoice, type Draft } from "@/lib/experts/draft";

/**
 * The browser this Expert's browse drives (Decision 0038 Z1). Shown while the draft grants
 * browse_goal, beside where it may go. The model never chooses it.
 */
export function BrowserField({
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
      id="browser"
      label="Browser"
      description="The stealth browser is real, headed Google Chrome in the same isolated box. It opens some sites that refuse a headless browser, and makes none of them allow automation: read a site's terms before listing it. It isn't for YouTube or Google."
    >
      {(control) => (
        <Select
          {...control}
          value={draft.browser}
          disabled={held}
          className="sm:max-w-xs"
          onChange={(event) => {
            const browser = browserChoice(event.target.value);
            if (browser !== null) onChange({ ...draft, browser });
          }}
        >
          {BROWSERS.map((option) => (
            <option key={option.kind} value={option.kind}>
              {option.label}
            </option>
          ))}
        </Select>
      )}
    </Field>
  );
}
