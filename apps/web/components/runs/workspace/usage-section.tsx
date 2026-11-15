import type { RunWorkspace } from "@autobots/api-client";
import { memo } from "react";

import { HairlineSection } from "@/components/ui/section";
import { formatUsd } from "@/lib/format";

/** What the run has done and spent, and the known unknowns, which stay visible when it ends. */
export const UsageSection = memo(function UsageSection({
  snapshot,
  unsettled,
}: {
  snapshot: RunWorkspace;
  unsettled: number;
}) {
  const { usage, outstanding, run } = snapshot;
  return (
    <HairlineSection id="usage-heading" title="Usage">
      <p className="text-ui leading-relaxed tabular-nums">
        {usage.model_calls} model calls, {usage.tool_dispatches} tool calls,{" "}
        {usage.repairs} repairs. Spent {formatUsd(run.budget.spent_micro_usd)}{" "}
        of {formatUsd(run.budget.limit_micro_usd)}, with{" "}
        {formatUsd(run.budget.reserved_micro_usd)} reserved.
      </p>
      {unsettled === 0 ? null : (
        <p
          data-outstanding="true"
          className="text-ui leading-relaxed tabular-nums"
        >
          Not settled: {outstanding.uncertain_calls} model calls with unknown
          outcomes, {outstanding.unknown_effects} tool effects with unknown
          outcomes, {outstanding.unreported_charges} calls with no reported
          charge.
        </p>
      )}
    </HairlineSection>
  );
});
