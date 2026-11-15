import type { ToolCatalog, ToolDescriptor } from "@autobots/api-client";

import { LEGEND } from "@/components/expert-editor/legend";
import { Choice } from "@/components/ui/field";
import type { Draft } from "@/lib/experts/draft";
import {
  grantable,
  toolGrant,
  toolGrantLabel,
  unavailableText,
  withTool,
} from "@/lib/experts/grants";

/** One tool's checkbox, and why it can't be granted when unavailable (PRD-Tool-Catalog TS-03). */
function ToolGrant({
  tool,
  draft,
  held,
  onChange,
}: {
  tool: ToolDescriptor;
  draft: Draft;
  held: boolean;
  onChange: (draft: Draft) => void;
}) {
  const { checked, unavailable, locked } = toolGrant(tool, draft);
  const why = `grant-tool-${tool.tool_id}-why`;
  return (
    <div data-tool={tool.tool_id}>
      <label
        htmlFor={`grant-tool-${tool.tool_id}`}
        className="flex items-start gap-2.5 text-sm"
      >
        <Choice
          id={`grant-tool-${tool.tool_id}`}
          aria-describedby={unavailable ? why : undefined}
          type="checkbox"
          checked={checked}
          disabled={held || locked}
          className="mt-0.5 shrink-0"
          onChange={(event) =>
            onChange(withTool(draft, tool, event.target.checked))
          }
        />
        <span>{toolGrantLabel(tool)}</span>
      </label>
      {unavailable ? (
        <p
          id={why}
          className="text-muted-foreground ml-6.5 text-xs"
          data-field="unavailable"
        >
          {unavailableText(tool)}
        </p>
      ) : null}
    </div>
  );
}

/**
 * Each tool an Expert may be granted, from the same catalog the Tools page shows (PRD-Tool-Catalog
 * TC-06, TS-04).
 */
export function ToolGrants({
  catalog,
  draft,
  held,
  onChange,
}: {
  catalog: ToolCatalog | null;
  draft: Draft;
  held: boolean;
  onChange: (draft: Draft) => void;
}) {
  return (
    <fieldset className="space-y-2 border-t pt-5">
      <legend className={LEGEND}>Allowed tools</legend>
      <div className="grid gap-x-6 gap-y-2 @xl:grid-cols-2">
        {grantable(catalog).map((tool) => (
          <ToolGrant
            key={tool.tool_id}
            tool={tool}
            draft={draft}
            held={held}
            onChange={onChange}
          />
        ))}
      </div>
    </fieldset>
  );
}
