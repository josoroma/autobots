/**
 * The Studio's shared write bodies and words (WBLD-09): a session's, which the Experts list and the
 * Expert editor send, and a create's, which the Experts and Workflows lists send. One key per intent
 * until its outcome is known, so a lost reply says the write may have happened and a press resends
 * it (Decision 0027 D2). Pure and JSX-free, so `node --test` covers it.
 */
import type { SessionCreate } from "@autobots/api-client";

import { withHeld } from "./submit.ts";
import type { Submitted } from "./use-submit.ts";

/** A session with these Experts: direct with one, or a coordinator among several (US-5.1). */
export function sessionBody(
  kind: SessionCreate["kind"],
  expertIds: readonly string[],
): SessionCreate {
  return { kind, experts: expertIds.map((expert_id) => ({ expert_id })) };
}

export const SESSION_LOST =
  "The reply was lost, so the session may have started. Pressing again won't start a second one.";
export const SESSION_REFUSED = "That session could not be started.";

/** Why a session didn't open: its reply was lost, or it was refused. */
export function sessionText(
  result: Pick<Submitted<unknown>, "outcome" | "held">,
): string {
  return result.outcome === "unknown"
    ? SESSION_LOST
    : withHeld(SESSION_REFUSED, result.held);
}

export const CREATE_LOST =
  "The reply was lost, so it may have been created. Pressing again won't create a second one.";

/** Why a create didn't open its item: its reply was lost, or the screen's words for the refusal. */
export function createText(
  result: Pick<Submitted<unknown>, "outcome" | "refusal" | "held">,
  refusals: Readonly<Record<string, string>>,
): string {
  return result.outcome === "unknown"
    ? CREATE_LOST
    : withHeld(
        refusals[result.refusal?.code ?? ""] ?? "That could not be saved.",
        result.held,
      );
}
