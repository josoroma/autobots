import type { ModelCallView } from "@autobots/api-client";
import { CircleAlert } from "lucide-react";

import { InspectorSection } from "@/components/runs/inspector/inspector-section";
import { formatUsd } from "@/lib/format";
import { callCharge, callOutcome, tokens } from "@/lib/runs/inspector";

/** Every model call in this run's tree, which shares its budget. */
export function ModelCalls({ calls }: { calls: readonly ModelCallView[] }) {
  return (
    <InspectorSection
      id="calls-heading"
      title="Model calls"
      note="This run and any child runs, since they share its budget."
    >
      {calls.length === 0 ? (
        <p className="text-muted-foreground text-sm">No model calls.</p>
      ) : (
        <ul className="divide-y border-y text-sm">
          {calls.map((call) => (
            <ModelCallRow key={call.id} call={call} />
          ))}
        </ul>
      )}
    </InspectorSection>
  );
}

function ModelCallRow({ call }: { call: ModelCallView }) {
  const charge = callCharge(call);
  return (
    <li
      data-call={call.status}
      className="grid gap-x-6 gap-y-2 py-4 break-words md:grid-cols-[minmax(0,1fr)_15rem]"
    >
      <div className="min-w-0 space-y-1">
        <p className="font-medium">
          {call.role}, attempt {call.attempt}: {callOutcome(call)}
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
          Tokens: {tokens(call.input_tokens)} in, {tokens(call.output_tokens)}{" "}
          out, of which {tokens(call.reasoning_tokens)} reasoning.
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
        <p data-cost={charge.kind}>
          {charge.label} {charge.amount}
        </p>
        <p data-cost="estimated" className="text-muted-foreground">
          Estimated worst case, not a charge:{" "}
          {formatUsd(call.estimated_micro_usd)}
        </p>
      </div>
    </li>
  );
}
