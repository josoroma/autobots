import { memo } from "react";

import {
  ToolUsesState,
  ToolUseTable,
} from "@/components/runs/tool-uses/tool-use-table";
import { useToolUses } from "@/components/runs/tool-uses/use-tool-uses";
import { HairlineSection } from "@/components/ui/section";
import { toolOutcome } from "@/lib/runs/tool-uses";

/** The run workspace's section. `version` changes when a tool-use event arrives. */
export const ToolsUsed = memo(function ToolsUsed({
  runId,
  version,
}: {
  runId: string;
  version: number;
}) {
  const read = useToolUses(runId, version);
  const { uses } = read;
  const latest = uses?.at(-1);
  return (
    <HairlineSection id="tools-used-heading" title="Tools used">
      <p className="sr-only" aria-live="polite" data-field="tool-announcement">
        {latest === undefined
          ? ""
          : `${latest.tool_id}: ${toolOutcome(latest)}. ${uses?.length ?? 0} tool uses.`}
      </p>
      {uses === null || uses.length === 0 ? (
        <ToolUsesState uses={read} empty="No tool has been used yet." />
      ) : (
        <ToolUseTable uses={uses} caption="Tools this run used, in order" />
      )}
    </HairlineSection>
  );
});
