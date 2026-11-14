"use client";

import { parseRunInspector } from "@autobots/api-client";
import { CircleAlert } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { LoadState } from "@/components/ui/load-state";
import { PageHeader } from "@/components/ui/page-header";
import { RUN_NOT_FOUND } from "@/lib/run-workspace-load";
import { useResource } from "@/lib/use-resource";

function dollars(micro: number): string {
  return `US$${micro / 1_000_000}`;
}

function tokens(value: number | null): string {
  return value === null ? "not reported" : String(value);
}

// The run page's classification: a refusal, a missing run and a mismatch each say so, and only an
// outage offers Retry (WRUN-02, PRD-Development-Harness DH-06). It reads once; Retry reads again.
export function RunInspectorView({ runId }: { runId: string }) {
  const { state, pending, reload } = useResource(
    `/api/v1/runs/${encodeURIComponent(runId)}/inspector`,
    parseRunInspector,
  );
  if (state.kind !== "ready") {
    return (
      <div className="mx-auto max-w-4xl space-y-4">
        <PageHeader title="Run inspector" />
        <LoadState
          state={state}
          what="this run"
          onRetry={reload}
          pending={pending}
          notFound={RUN_NOT_FOUND}
        />
      </div>
    );
  }
  const view = state.value;
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header className="space-y-2">
        <h1 className="text-[32px] leading-tight">Run inspector</h1>
        <p className="text-muted-foreground text-sm leading-relaxed">
          <span className="text-foreground font-document text-[17px] break-words">
            {view.goal_summary === "" ? "Untitled run" : view.goal_summary}.
          </span>{" "}
          <Link
            href={`/runs/${runId}`}
            className="text-foreground font-medium whitespace-nowrap underline underline-offset-4"
          >
            Back to the run
          </Link>
        </p>
      </header>
      <Section
        id="calls-heading"
        title="Model calls"
        note="This run and any child runs, since they share its budget."
      >
        {view.model_calls.length === 0 ? (
          <p className="text-muted-foreground text-sm">No model calls.</p>
        ) : (
          <ul className="divide-y border-y text-sm">
            {view.model_calls.map((call) => (
              <li
                key={call.id}
                data-call={call.status}
                className="grid gap-x-6 gap-y-2 py-4 break-words md:grid-cols-[minmax(0,1fr)_15rem]"
              >
                <div className="min-w-0 space-y-1">
                  <p className="font-medium">
                    {call.role}, attempt {call.attempt}:{" "}
                    {call.outcome_unknown
                      ? "outcome unknown"
                      : call.charge_source_unknown
                        ? "reconciled"
                        : call.status.replaceAll("_", " ")}
                  </p>
                  <p className="text-muted-foreground text-xs">
                    Provider {call.provider}. Upstream{" "}
                    <span data-upstream="true" className="font-mono">
                      {call.upstream_provider}
                    </span>
                    .
                  </p>
                  <p className="text-muted-foreground text-xs">
                    Canonical{" "}
                    <span
                      data-canonical="true"
                      className="text-foreground font-mono break-all"
                    >
                      {call.canonical_id}
                    </span>
                    , wire{" "}
                    <span data-wire="true" className="font-mono break-all">
                      {call.wire_id}
                    </span>
                  </p>
                  <p className="text-muted-foreground text-xs tabular-nums">
                    Tokens: {tokens(call.input_tokens)} in,{" "}
                    {tokens(call.output_tokens)} out, of which{" "}
                    {tokens(call.reasoning_tokens)} reasoning.
                  </p>
                  {call.failure_class === null ? null : (
                    <p
                      data-error="true"
                      className="text-destructive flex items-start gap-1.5 text-xs"
                    >
                      <CircleAlert
                        aria-hidden="true"
                        className="mt-px size-3.5 shrink-0"
                      />
                      Error: {call.failure_class.replaceAll("_", " ")}
                    </p>
                  )}
                </div>
                <div className="min-w-0 space-y-1 text-xs tabular-nums md:border-l md:pl-4">
                  {call.reconciled ? (
                    <p data-cost="entered">
                      Charge entered by the owner, from the provider&apos;s
                      records:{" "}
                      {call.reported_micro_usd === null
                        ? "none"
                        : dollars(call.reported_micro_usd)}
                    </p>
                  ) : call.charge_source_unknown ? (
                    <p data-cost="unattributed">
                      Charge reconciled, source not recorded:{" "}
                      {call.reported_micro_usd === null
                        ? "none"
                        : dollars(call.reported_micro_usd)}
                    </p>
                  ) : (
                    <p data-cost="reported">
                      Reported charge:{" "}
                      {call.reported_micro_usd === null
                        ? "none"
                        : dollars(call.reported_micro_usd)}
                    </p>
                  )}
                  <p data-cost="estimated" className="text-muted-foreground">
                    Estimated worst case, not a charge:{" "}
                    {dollars(call.estimated_micro_usd)}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Section>
      <Section
        id="tools-heading"
        title="Tool operation attempts"
        note="This run only. A child run shows its own."
      >
        {view.tool_attempts.length === 0 ? (
          <p className="text-muted-foreground text-sm">No tool operations.</p>
        ) : (
          <ul className="divide-y border-y text-sm">
            {view.tool_attempts.map((attempt) => (
              <li
                key={attempt.operation_id}
                data-tool={attempt.tool_id}
                data-tool-status={attempt.status}
                className="py-2 break-words"
              >
                <code className="font-mono text-[13px] font-medium break-all">
                  {attempt.tool_id}
                </code>
                <span className="text-muted-foreground">
                  , version {attempt.tool_version}:{" "}
                </span>
                {attempt.status}
                {attempt.failure_code === null
                  ? ""
                  : ` (${attempt.failure_code})`}
              </li>
            ))}
          </ul>
        )}
      </Section>
      <Section id="evidence-heading" title="Evidence">
        {view.evidence.length === 0 ? (
          <p data-field="evidence" className="text-muted-foreground text-sm">
            No task has cited evidence.
          </p>
        ) : (
          <ul data-field="evidence" className="divide-y border-y text-sm">
            {view.evidence.map((item) => (
              <li
                key={`${item.task_id}-${item.reference}`}
                className="space-y-1 py-3 break-words"
              >
                <p>
                  <span className="text-muted-foreground">
                    Task{" "}
                    <span className="font-mono text-xs break-all">
                      {item.task_id}
                    </span>
                    :
                  </span>{" "}
                  <span className="font-document text-[15px] leading-relaxed">
                    {item.summary}
                  </span>
                </p>
                <p className="font-mono text-xs break-all">
                  {item.kind === "artifact" && item.artifact_id !== null ? (
                    <a
                      href={`/api/v1/artifacts/${item.artifact_id}/download`}
                      className="font-medium underline underline-offset-4"
                    >
                      {item.reference}
                    </a>
                  ) : (
                    <span className="text-muted-foreground">
                      {`${item.kind}: ${item.reference}`}
                    </span>
                  )}
                </p>
              </li>
            ))}
          </ul>
        )}
      </Section>
      <Section id="checkpoints-heading" title="Checkpoints">
        {view.checkpoints.length === 0 ? (
          <p className="text-muted-foreground text-sm">No checkpoints.</p>
        ) : (
          <ol className="divide-y border-y text-sm">
            {view.checkpoints.map((checkpoint) => (
              <li
                key={checkpoint.checkpoint_id}
                data-checkpoint={checkpoint.checkpoint_id}
                className="py-2 break-all"
              >
                Step {checkpoint.step ?? "not recorded"},{" "}
                {checkpoint.source ?? "unknown source"}:{" "}
                <span className="text-muted-foreground font-mono text-xs">
                  {checkpoint.checkpoint_id}
                </span>
              </li>
            ))}
          </ol>
        )}
        {view.checkpoints_truncated ? (
          <p className="text-muted-foreground text-sm">
            Showing the first {view.checkpoints.length} checkpoints.
          </p>
        ) : null}
      </Section>
    </div>
  );
}

// Decision 0021: a hairline-separated section in place of a card, with an optional muted line under its heading.
function Section({
  id,
  title,
  note,
  children,
}: {
  id: string;
  title: string;
  note?: string;
  children: ReactNode;
}) {
  return (
    <section aria-labelledby={id} className="space-y-3 border-t pt-6">
      <div className="space-y-1">
        <h2 id={id} className="text-sm font-semibold">
          {title}
        </h2>
        {note === undefined ? null : (
          <p className="text-muted-foreground text-sm">{note}</p>
        )}
      </div>
      {children}
    </section>
  );
}
