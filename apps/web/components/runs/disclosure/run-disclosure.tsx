"use client";

import {
  DataNotice,
  DisclosureNotice,
  ModelAndBudget,
  ModelChoice,
  RoleDetails,
} from "@/components/runs/disclosure/disclosure-parts";
import { useDisclosureReads } from "@/components/runs/disclosure/use-disclosure-reads";
import { FALLBACK_BUDGET_MICRO_USD } from "@/lib/budget";
import {
  canonicalOf,
  resolveDisclosure,
  WORKSPACE_DEFAULT,
} from "@/lib/runs/disclosure";

// MP-07. Every screen that creates a run shows this, and reading it starts nothing.
export function RunDisclosure({
  chosen,
  onChoose,
  roleOverrides,
  // A screen that sends no budget runs with RunRequest's default limit, US$1.00 as D11's default is.
  budgetMicroUsd = FALLBACK_BUDGET_MICRO_USD,
  sendsOnlyIfAgent = false,
  usesModel = true,
}: {
  // Absent where a screen offers no per-run choice.
  chosen?: string;
  onChoose?: (profile: string) => void;
  // An Expert's own role bindings, which a run-wide choice doesn't replace.
  roleOverrides?: Readonly<Record<string, unknown>> | undefined;
  budgetMicroUsd?: number;
  sendsOnlyIfAgent?: boolean;
  // False for a workflow version with no agent step, which calls no model and isn't refused.
  usesModel?: boolean;
}) {
  const reads = useDisclosureReads();
  const chosenProfile = chosen ?? WORKSPACE_DEFAULT;
  const shown = resolveDisclosure({
    ...reads,
    chosen: chosenProfile,
    roleOverrides,
    usesModel,
  });
  const canonical = (profile: string) => canonicalOf(reads.models, profile);
  return (
    <div data-field="disclosure" className="flex flex-col gap-3 text-sm">
      {onChoose === undefined || reads.models === null ? null : (
        <ModelChoice
          models={reads.models}
          chosen={chosenProfile}
          onChoose={onChoose}
        />
      )}
      <DisclosureNotice failed={reads.failed} shown={shown} />
      <ModelAndBudget
        model={
          shown.showModel && shown.executor !== null
            ? canonical(shown.executor.profile)
            : null
        }
        budgetMicroUsd={budgetMicroUsd}
        local={reads.source === "local"}
      />
      {shown.showModel ? (
        <RoleDetails bindings={shown.bindings} canonical={canonical} />
      ) : null}
      <DataNotice
        sendsOnlyIfAgent={sendsOnlyIfAgent}
        local={reads.source === "local"}
      />
    </div>
  );
}
