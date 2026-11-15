import type { RunWorkspace } from "@autobots/api-client";
import { memo } from "react";

import { Section } from "@/components/runs/workspace/section";
import { formatUsd } from "@/lib/format";

/** MP-07's limits this run works under, and what it has used of them. */
export const BudgetsSection = memo(function BudgetsSection({
  snapshot,
  contextThousands,
}: {
  snapshot: RunWorkspace;
  contextThousands: number;
}) {
  const { budgets, usage, run } = snapshot;
  return (
    <Section id="budgets-heading" title="Budgets">
      <div
        data-field="budgets"
        className="space-y-2 text-[13px] leading-relaxed tabular-nums"
      >
        <p>
          Tokens: up to {budgets.max_output_tokens_per_call} output tokens per
          call, and about {contextThousands}K tokens of context. Used so far:{" "}
          {usage.input_tokens} in, {usage.output_tokens} out.
        </p>
        <p>
          Spend limit: {formatUsd(run.budget.limit_micro_usd)}. Reported so far:{" "}
          {formatUsd(run.budget.spent_micro_usd)}. Held as an estimate for calls
          not settled: {formatUsd(run.budget.reserved_micro_usd)}.{" "}
          <span className="text-muted-foreground">
            The workspace&apos;s per-run and daily limits apply too, and the
            lowest one stops the run.
          </span>
        </p>
      </div>
    </Section>
  );
});
