import { memo } from "react";

import {
  ToolUsesState,
  ToolUseTable,
} from "@/components/runs/tool-uses/tool-use-table";
import { useToolUses } from "@/components/runs/tool-uses/use-tool-uses";
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
    <section
      aria-labelledby="tools-used-heading"
      className="space-y-3 border-t pt-6"
    >
      <h2 id="tools-used-heading" className="text-sm font-semibold">
        Tools used
      </h2>
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
    </section>
  );
});
