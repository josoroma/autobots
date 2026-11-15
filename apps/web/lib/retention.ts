/**
 * A retention window as typed in Operations: empty keeps everything, otherwise whole days only.
 * A lenient parse saved "1,000" as 1 day, which feeds an irreversible retention pass (WSYS-01).
 * The contract owns each window's range and the service the cross-field rule; this refuses
 * malformed text and checks the range with the generated parser, never a copy of it.
 */
import {
  parseRetentionSettings,
  type RetentionSettings,
} from "@autobots/api-client";

import { refusalText } from "./submit.ts";

export type Days = { valid: true; days: number | null } | { valid: false };

export function parseDays(text: string): Days {
  const value = text.trim();
  if (value === "") return { valid: true, days: null };
  if (!/^\d+$/.test(value)) return { valid: false };
  const days = Number(value);
  return Number.isSafeInteger(days) ? { valid: true, days } : { valid: false };
}

function allowed(
  field: "run_days" | "receipt_days",
  days: number | null,
): boolean {
  try {
    parseRetentionSettings({ [field]: days });
    return true;
  } catch {
    return false;
  }
}

export interface RetentionRequest {
  /** The request's body, or null when either window was refused, so nothing is sent. */
  body: RetentionSettings | null;
  invalid: { run: boolean; receipt: boolean };
}

/** Both windows as typed, read into one request, or marked where they were refused. */
export function retentionRequest(
  runText: string,
  receiptText: string,
): RetentionRequest {
  const run = parseDays(runText);
  const receipt = parseDays(receiptText);
  // Each window is checked on its own, so both are marked when both are refused.
  const invalid = {
    run: !run.valid || !allowed("run_days", run.days),
    receipt: !receipt.valid || !allowed("receipt_days", receipt.days),
  };
  if (invalid.run || invalid.receipt || !run.valid || !receipt.valid) {
    return { body: null, invalid };
  }
  return {
    body: { run_days: run.days, receipt_days: receipt.days },
    invalid,
  };
}

export const RETENTION_SAVED =
  "Saved. Nothing is removed until the next retention pass.";

// R-19 step 4: this screen's words for a refusal's code. The page already refuses malformed and
// out-of-range days, so an invalid request is the pairing rule.
const RETENTION_REFUSALS: Readonly<Record<string, string>> = {
  invalid_request: "Retry keys need a run content window at least as short.",
};
const RETENTION_LOST =
  "The reply was lost, so this may have saved. Saving again sends these windows again.";

/** What a save says: saved, refused with the service's reason, or that its reply was lost. */
export function retentionOutcome(
  accepted: boolean,
  refusal: { code: string; message: string } | null,
): string {
  if (accepted) return RETENTION_SAVED;
  return refusal === null
    ? RETENTION_LOST
    : `Not saved. ${refusalText(RETENTION_REFUSALS, refusal, RETENTION_LOST)}`;
}
