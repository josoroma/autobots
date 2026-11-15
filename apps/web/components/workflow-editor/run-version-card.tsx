import {
  parseRunPreview,
  type RunPreview,
  type WorkflowView,
} from "@autobots/api-client";
import { Play } from "lucide-react";

import { HeldNote } from "@/components/held-note";
import { RunDisclosure } from "@/components/run-disclosure";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Select, Textarea } from "@/components/ui/field";
import { LoadState } from "@/components/ui/load-state";
import { FIELD_LABEL } from "@/components/workflow-editor/field-label";
import { useVersionRun } from "@/components/workflow-editor/use-version-run";
import { budgetOffer, type BudgetOffer } from "@/lib/budget";
import { formatUsd } from "@/lib/format";
import { useResource, type Resource } from "@/lib/use-resource";
import { cn } from "@/lib/utils";

const UNKNOWN: BudgetOffer = { kind: "unknown" };

/**
 * The same budget choices as a goal run, from what's left of today's cap (PRD-Studio WF-05,
 * Decision 0022 D11). Nothing shows while they're read, and a failed read says so with Retry
 * (WBLD-04); a run then sends no budget, so the service applies its default.
 */
function BudgetField({
  preview,
  offer,
  budget,
  disabled,
  onChoose,
}: {
  preview: Resource<RunPreview>;
  offer: BudgetOffer;
  budget: number;
  disabled: boolean;
  onChoose: (budget: number) => void;
}) {
  const { state } = preview;
  if (state.kind === "idle" || state.kind === "loading") return null;
  if (state.kind !== "ready") {
    return (
      <LoadState
        state={state}
        what="today's budget choices"
        onRetry={preview.reload}
        pending={preview.pending}
      />
    );
  }
  if (offer.kind === "unknown") return null;
  return (
    <div className="space-y-1.5">
      <label htmlFor="execution-budget" className={FIELD_LABEL}>
        Budget
      </label>
      <Select
        id="execution-budget"
        value={offer.choices.length === 0 ? "" : String(budget)}
        disabled={offer.choices.length === 0 || disabled}
        onChange={(event) => onChoose(Number(event.target.value))}
        className="tabular-nums sm:max-w-40"
      >
        {offer.choices.length === 0 ? (
          <option value="">Nothing left today</option>
        ) : (
          offer.choices.map((value) => (
            <option key={value} value={String(value)}>
              {formatUsd(value)}
            </option>
          ))
        )}
      </Select>
    </div>
  );
}

/** Starts an execution of a published version; a draft can't be run (PRD-Studio WF-02). */
export function RunVersionCard({
  workflow,
  className,
}: {
  workflow: WorkflowView;
  className?: string;
}) {
  const preview = useResource("/api/v1/run-preview", parseRunPreview);
  const offer =
    preview.state.kind === "ready"
      ? budgetOffer(preview.state.value.budget)
      : UNKNOWN;
  const run = useVersionRun(workflow, offer);
  return (
    <Card
      aria-labelledby="run-heading"
      className={cn("space-y-4 p-6", className)}
    >
      <h2
        id="run-heading"
        className="font-serif text-[22px] leading-tight font-normal tracking-tight"
      >
        Run a version
      </h2>
      {workflow.versions.length === 0 ? (
        <p className="text-muted-foreground text-sm">
          Publish a version first.
        </p>
      ) : (
        <>
          <div className="space-y-1.5">
            <label htmlFor="version" className={FIELD_LABEL}>
              Version
            </label>
            <Select
              id="version"
              value={run.version ?? ""}
              disabled={run.held}
              onChange={(event) => run.choose(Number(event.target.value))}
              className="sm:max-w-md"
            >
              {workflow.versions.map((version) => (
                <option key={version.version} value={version.version}>
                  Version {version.version}, {version.graph_hash.slice(0, 12)}
                  {version.source === "model_proposal" ? ", from a model" : ""}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <label htmlFor="inputs" className={FIELD_LABEL}>
              Inputs
            </label>
            <Textarea
              id="inputs"
              rows={3}
              spellCheck={false}
              value={run.inputs}
              readOnly={run.held}
              onChange={(event) => run.setInputs(event.target.value)}
              className="font-mono text-[12.5px] leading-relaxed"
            />
          </div>
          <BudgetField
            preview={preview}
            offer={offer}
            budget={run.budget}
            disabled={run.held}
            onChoose={run.chooseBudget}
          />
          <RunDisclosure
            budgetMicroUsd={run.budget}
            sendsOnlyIfAgent
            usesModel={
              workflow.versions
                .find((version) => version.version === run.version)
                ?.graph.nodes?.some((node) => node.block === "agent") ?? false
            }
          />
          {run.held ? <HeldNote /> : null}
          {run.message === null ? null : (
            <p role="status" data-message="run" className="text-sm">
              {run.message}
            </p>
          )}
          <div className="flex justify-end border-t pt-4">
            <Button onClick={() => void run.run()} disabled={run.pending}>
              <Play aria-hidden="true" />
              Run this version
            </Button>
          </div>
        </>
      )}
    </Card>
  );
}
