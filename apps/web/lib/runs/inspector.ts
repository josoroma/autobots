/**
 * How the run inspector states one model call: its outcome, its tokens, and which charge it has,
 * which is never added to the estimate (PRD-Development-Harness DH-06). Pure and JSX-free.
 */
import type { ModelCallView } from "@autobots/api-client";

import { formatUsd } from "../format.ts";

export function tokens(value: number | null): string {
  return value === null ? "not reported" : String(value);
}

/** The call's outcome: unknown, reconciled with no recorded source, or its status in words. */
export function callOutcome(call: ModelCallView): string {
  if (call.outcome_unknown) return "outcome unknown";
  if (call.charge_source_unknown) return "reconciled";
  return call.status.replaceAll("_", " ");
}

export interface CallCharge {
  /** `data-cost`: an owner's entry, a reconciliation from before sources were recorded, or a report. */
  kind: "entered" | "unattributed" | "reported";
  label: string;
  amount: string;
}

export function callCharge(call: ModelCallView): CallCharge {
  const amount =
    call.reported_micro_usd === null
      ? "none"
      : formatUsd(call.reported_micro_usd);
  if (call.reconciled)
    return {
      kind: "entered",
      label: "Charge entered by the owner, from the provider's records:",
      amount,
    };
  if (call.charge_source_unknown)
    return {
      kind: "unattributed",
      label: "Charge reconciled, source not recorded:",
      amount,
    };
  return { kind: "reported", label: "Reported charge:", amount };
}
