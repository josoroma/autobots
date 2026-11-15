import type { WorkflowStepView } from "@autobots/api-client";
import { ShieldCheck } from "lucide-react";

/** An agent step's Expert, model and tools, as the version binds them. */
function AgentFacts({ step }: { step: WorkflowStepView }) {
  return (
    <dl className="text-muted-foreground mt-1 grid gap-x-3 gap-y-0.5 text-[12.5px] sm:grid-cols-[auto_1fr]">
      <dt>Expert</dt>
      <dd data-field="step-expert" className="text-foreground">
        {step.expert_name ?? "Unavailable"}
      </dd>
      <dt>Model</dt>
      <dd data-field="step-model" className="text-foreground font-mono">
        {step.model ?? "Unknown"}
      </dd>
      <dt>Tools</dt>
      <dd data-field="step-tools" className="text-foreground font-mono">
        {step.tools.length === 0 ? "None" : step.tools.join(", ")}
      </dd>
    </dl>
  );
}

/** The shown version's steps in order, with each approval gate said in words (PRD-Studio WF-03). */
export function PreviewSteps({
  steps,
}: {
  steps: readonly WorkflowStepView[];
}) {
  return (
    <ol data-field="preview-steps" className="space-y-2 text-[13.5px]">
      {steps.map((step, index) => (
        <li
          key={step.id}
          data-step={step.id}
          className="border-border rounded-lg border px-3.5 py-2.5"
        >
          <p>
            <span className="text-muted-foreground tabular-nums">
              {index + 1}.
            </span>{" "}
            <span className="font-medium">{step.label ?? step.id}</span>{" "}
            <span className="text-muted-foreground font-mono text-[12px]">
              {step.block}
            </span>
          </p>
          {step.approval ? (
            <p
              data-field="approval-gate"
              className="mt-1 flex items-center gap-1.5 text-[13px] font-medium"
            >
              <ShieldCheck aria-hidden="true" className="size-3.5" />
              Approval gate: a person approves before the run continues.
            </p>
          ) : null}
          {step.block === "agent" ? <AgentFacts step={step} /> : null}
        </li>
      ))}
    </ol>
  );
}
