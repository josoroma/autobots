import type { ToolCatalog } from "@autobots/api-client";

import { LEGEND } from "@/components/expert-editor/legend";
import { Choice } from "@/components/ui/field";
import { LoadState } from "@/components/ui/load-state";
import type { Draft } from "@/lib/experts/draft";
import {
  grantGroups,
  groupGrantLabel,
  groupLocked,
  withGroup,
} from "@/lib/experts/grants";
import type { Resource } from "@/lib/use-resource";

/**
 * Whole groups an Expert may be granted (PRD-Tool-Catalog TC-06). A group holding an unavailable
 * tool can be unchecked but not checked. The catalog's read has its own loading and unavailable
 * states.
 */
export function GroupGrants({
  catalog,
  draft,
  held,
  onChange,
}: {
  catalog: Resource<ToolCatalog>;
  draft: Draft;
  held: boolean;
  onChange: (draft: Draft) => void;
}) {
  return (
    <fieldset className="space-y-2 border-t pt-5" data-field="tool-groups">
      <legend className={LEGEND}>Grant whole groups</legend>
      {catalog.value === null ? (
        <LoadState
          state={catalog.state}
          what="the tool catalog"
          onRetry={catalog.reload}
          pending={catalog.pending}
        />
      ) : (
        <div className="grid gap-x-6 gap-y-2 @xl:grid-cols-2">
          {grantGroups(catalog.value).map((group) => {
            const checked = draft.groups.includes(group.group);
            return (
              <label
                key={group.group}
                htmlFor={`grant-group-${group.group}`}
                className="flex items-start gap-2.5 text-sm"
              >
                <Choice
                  id={`grant-group-${group.group}`}
                  type="checkbox"
                  checked={checked}
                  disabled={held || groupLocked(group, checked)}
                  className="mt-0.5 shrink-0"
                  onChange={(event) =>
                    onChange(
                      withGroup(draft, group.group, event.target.checked),
                    )
                  }
                />
                <span>{groupGrantLabel(group)}</span>
              </label>
            );
          })}
        </div>
      )}
    </fieldset>
  );
}
