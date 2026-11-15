/**
 * The run vocabulary every screen shares, keyed by the generated RunStatus so that a status the
 * contract gains fails the type check here until it has words, a tone and a terminal flag (R-37,
 * XTYP-06, XWEB-08). Presentation only: the service owns the transitions, and sends the commands a
 * run offers as RunWorkspace.allowed_commands (`commands.ts`). Pure and JSX-free;
 * `components/runs/run-state.tsx` draws the tones.
 */
import type { RunStatus } from "@autobots/api-client";

/** Short state words, for the run list, the run page's header, Home and Workflows. */
export const RUN_STATUS_LABEL: Readonly<Record<RunStatus, string>> = {
  queued: "Queued",
  running: "Running",
  waiting_input: "Waiting for input",
  waiting_approval: "Waiting for approval",
  paused: "Paused",
  verifying: "Verifying",
  cancelling: "Cancelling",
  succeeded: "Succeeded",
  failed: "Failed",
  cancelled: "Cancelled",
};

/** The run page's status sentence. A stop reason is said apart from it, so a state can say why. */
export const RUN_STATUS_SENTENCE: Readonly<Record<RunStatus, string>> = {
  queued: "Queued. Waiting for a worker.",
  running: "Running.",
  waiting_input: "Waiting for your input.",
  waiting_approval: "Waiting for an approval decision.",
  paused: "Paused. No new work starts until it resumes.",
  verifying: "Checking the result against its criteria.",
  cancelling: "Cancelling. Active work is being settled.",
  succeeded: "Succeeded.",
  failed: "Failed.",
  cancelled: "Cancelled.",
};

export type RunTone = "live" | "attention" | "success" | "failure" | "idle";

// Decision 0021 R3–R4: what runs is live, what waits for a person takes the attention tone, a
// failure is destructive, and the rest stay neutral. A tone always sits beside the state's words.
const TONE: Readonly<Record<RunStatus, RunTone>> = {
  queued: "idle",
  running: "live",
  waiting_input: "attention",
  waiting_approval: "attention",
  paused: "idle",
  verifying: "live",
  cancelling: "idle",
  succeeded: "success",
  failed: "failure",
  cancelled: "idle",
};

export function runTone(status: RunStatus): RunTone {
  return TONE[status];
}

// SP-010: a terminal run can't resume. The same three as TERMINAL in the service's domain/runs.py.
const TERMINAL: Readonly<Record<RunStatus, boolean>> = {
  queued: false,
  running: false,
  waiting_input: false,
  waiting_approval: false,
  paused: false,
  verifying: false,
  cancelling: false,
  succeeded: true,
  failed: true,
  cancelled: true,
};

/** A value a contract field types as a string, such as ExecutionView.run_status, that names a run status. */
export function isRunStatus(value: string): value is RunStatus {
  return Object.hasOwn(RUN_STATUS_LABEL, value);
}

/** Whether a run has ended for good. A value that isn't a run status hasn't. */
export function isTerminal(status: string): boolean {
  return isRunStatus(status) && TERMINAL[status];
}

/** The short words for a status a contract field types as a string, or the value as sent. */
export function runStatusText(status: string): string {
  return isRunStatus(status) ? RUN_STATUS_LABEL[status] : status;
}

/** A stop code's words, as the run page, the run list and the workflow monitor all say them. */
export function stopReasonText(code: string): string {
  return code.replaceAll("_", " ");
}
