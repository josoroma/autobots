import {
  NO_EXPERT,
  type OptionsRead,
  type RunOptions,
} from "@/components/composer/use-run-options";
import { Select } from "@/components/ui/field";
import { LoadState } from "@/components/ui/load-state";
import type { BudgetChoices } from "@/lib/budget";
import { formatUsd } from "@/lib/format";
import { worstFailure } from "@/lib/load";
import { cn } from "@/lib/utils";

// Chips read as one row of compact, labelled native selects (Decision 0021: no box shadows).
// A chip wraps its label above the select when narrow, and the select shrinks to the row, so nothing
// scrolls sideways at 400% zoom. The select keeps its own right padding for the chevron.
const CHIP =
  "flex min-w-0 max-w-full flex-wrap items-center gap-x-1.5 gap-y-1 text-ui";
const CHIP_CONTROL = "min-w-0 max-w-full";
const CHIP_SELECT =
  "h-8 w-auto max-w-full truncate rounded-full py-0 pl-3 text-ui leading-8";

/** The budget's options: the default while no range is known, the range, or that nothing is left. */
function BudgetOptions({ budget }: { budget: BudgetChoices }) {
  if (budget.offer.kind === "unknown") {
    return (
      <option value={String(budget.budget)}>{formatUsd(budget.budget)}</option>
    );
  }
  if (budget.exhausted) return <option value="">Nothing left today</option>;
  return budget.offer.choices.map((value) => (
    <option key={value} value={String(value)}>
      {formatUsd(value)}
    </option>
  ));
}

/**
 * Why a chip's list can't be read, on a line of its own under the chips, with Retry for an outage
 * (PRD-Development-Harness DH-06). Nothing while the read loads or once it's ready, as the chip
 * offers its default meanwhile. During a Retry the failure stays, and Retry waits.
 */
function ReadFailure({ read, what }: { read: OptionsRead; what: string }) {
  const failure = worstFailure([read.state]);
  if (failure === null) return null;
  return (
    <LoadState
      state={failure}
      what={what}
      onRetry={read.reload}
      pending={read.pending}
      className="basis-full"
    />
  );
}

/**
 * The model, Expert and budget chips, and what's left of today's cap (PRD-Studio HM-02, Decision
 * 0022 D11). While a request is held, each stays as it was sent (Decision 0027 D2). A list that
 * can't be read says why after the chips.
 */
export function RunOptionChips({
  options,
  budget,
  held,
}: {
  options: RunOptions;
  budget: BudgetChoices;
  held: boolean;
}) {
  return (
    <div
      role="group"
      aria-label="Run options"
      data-field="composer-chips"
      className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t px-5 py-3"
    >
      <div className={CHIP} data-chip="models">
        <label htmlFor="run-model" className="text-muted-foreground">
          Model for this run
        </label>
        <div className={CHIP_CONTROL}>
          <Select
            id="run-model"
            value={options.profile}
            disabled={held}
            onChange={(event) => options.chooseProfile(event.target.value)}
            className={CHIP_SELECT}
          >
            <option value="">The workspace setting</option>
            {options.models.map((model) => (
              <option key={model.profile} value={model.profile}>
                {model.canonical_id}
              </option>
            ))}
          </Select>
        </div>
      </div>
      <div className={CHIP} data-chip="expert">
        <label htmlFor="run-expert" className="text-muted-foreground">
          Expert
        </label>
        <div className={CHIP_CONTROL}>
          <Select
            id="run-expert"
            value={options.expertId}
            disabled={held}
            onChange={(event) => options.chooseExpert(event.target.value)}
            className={CHIP_SELECT}
          >
            <option value={NO_EXPERT}>No Expert, a goal run</option>
            {options.experts.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </Select>
        </div>
      </div>
      <div className={CHIP} data-chip="budget">
        <label htmlFor="run-budget" className="text-muted-foreground">
          Budget
        </label>
        <div className={CHIP_CONTROL}>
          <Select
            id="run-budget"
            value={budget.exhausted ? "" : String(budget.budget)}
            disabled={budget.exhausted || held}
            onChange={(event) =>
              options.chooseBudget(Number(event.target.value))
            }
            className={cn(CHIP_SELECT, "tabular-nums")}
          >
            <BudgetOptions budget={budget} />
          </Select>
        </div>
      </div>
      {budget.remainingMicroUsd === null ? null : (
        <p
          data-field="daily-left"
          className="text-muted-foreground text-meta tabular-nums"
        >
          {formatUsd(budget.remainingMicroUsd)} left of today&apos;s cap
        </p>
      )}
      <ReadFailure read={options.reads.models} what="models" />
      <ReadFailure read={options.reads.experts} what="Experts" />
    </div>
  );
}
