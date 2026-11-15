/**
 * Starting the composer's run (PRD-Studio HM-02): with an Expert, a direct session first, then one
 * admission. One key until the outcome is known, and one press at a time (Decision 0027 D2). What
 * the card says comes from run-admission's one table (R-18).
 */
import {
  parseRunAccepted,
  parseSessionView,
  type RunAccepted,
  type RunRequest,
  type SessionCreate,
} from "@autobots/api-client";
import { useState } from "react";

import { NO_EXPERT } from "@/components/composer/use-run-options";
import type { Attached } from "@/lib/attachments";
import { csrfFetch } from "@/lib/csrf-fetch";
import { profileField } from "@/lib/model-profile";
import { readReply } from "@/lib/replies";
import {
  ADMISSION_UNKNOWN,
  admissionKind,
  admissionRefusal,
  type AdmissionRefusal,
  CHOICE_NOT_OFFERED,
} from "@/lib/run-admission";
import { withHeld } from "@/lib/submit";
import { type Submitted, useSubmit } from "@/lib/use-submit";

/**
 * What the card says after Run. `kind` is the screen's own name for it, which tests read as
 * `data-outcome`. An admitted run carries its id, so the two can't disagree; the run's own state
 * stays RunAccepted.status, never a second one here (WCMP-03).
 */
export type Said =
  | { kind: "queued"; outcome: "accepted"; text: string; runId: string | null }
  | {
      kind:
        AdmissionRefusal | "unknown" | "session_failed" | "choice_not_offered";
      outcome: "refused" | "unknown";
      text: string;
      /** A refusal settings can fix, which links there. */
      fix?: AdmissionRefusal;
    };

/** What one press sends, as the composer shows it at that press. */
export interface RunInputs {
  goal: string;
  profile: string;
  expertId: string;
  budget: number;
  files: readonly Attached[];
}

export interface RunAdmission {
  /** What the card says, or null before a press and while one is answered. */
  said: Said | null;
  pending: boolean;
  /** A request is held, so everything it sent stays as sent (Decision 0027 D2). */
  held: boolean;
  run: (inputs: RunInputs) => Promise<void>;
}

const KEPT = "Your draft is kept.";
const SESSION_FAILED: Said = {
  kind: "session_failed",
  outcome: "refused",
  text: `The Expert's session could not be started, so no run started. ${KEPT}`,
};
const CHOICE_REFUSED: Said = {
  kind: "choice_not_offered",
  outcome: "refused",
  text: CHOICE_NOT_OFFERED,
};

function saidFor(result: Submitted<RunAccepted>): Said {
  if (result.outcome === "accepted") {
    return {
      kind: "queued",
      outcome: "accepted",
      text: "Your goal is queued.",
      runId: result.value?.run_id ?? null,
    };
  }
  if (result.outcome === "unknown") {
    return {
      kind: "unknown",
      outcome: "unknown",
      text: `${ADMISSION_UNKNOWN} ${KEPT}`,
    };
  }
  const kind = admissionKind(result.refusal, result.status);
  return {
    kind,
    outcome: "refused",
    fix: kind,
    text: withHeld(
      `${admissionRefusal(result.refusal, result.status)} ${KEPT}`,
      result.held,
    ),
  };
}

// PRD-Studio HM-02: with an Expert, a direct session starts first and the run belongs to it.
async function startSession(expertId: string): Promise<string | null> {
  const reply = await csrfFetch("/api/v1/sessions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": crypto.randomUUID(),
    },
    body: JSON.stringify({
      kind: "direct",
      experts: [{ expert_id: expertId }],
    } satisfies SessionCreate),
  }).catch(() => null);
  if (reply?.ok !== true) {
    await reply?.text().catch(() => null);
    return null;
  }
  return (await readReply(reply, parseSessionView))?.id ?? null;
}

function runBody(
  inputs: RunInputs,
  field: NonNullable<ReturnType<typeof profileField>>,
  sessionId: string | null,
): string {
  return JSON.stringify({
    goal_text: inputs.goal,
    budget_micro_usd: inputs.budget,
    ...(sessionId === null ? {} : { session_id: sessionId }),
    ...field,
    ...(inputs.files.length === 0
      ? {}
      : {
          input_documents: inputs.files.map(
            ({ path, content, media_type }) => ({ path, content, media_type }),
          ),
        }),
  } satisfies RunRequest);
}

/** `onAccepted` runs once a run is admitted, before the card says so, such as to drop its files. */
export function useRunAdmission(onAccepted: () => void): RunAdmission {
  const admission = useSubmit();
  const [said, setSaid] = useState<Said | null>(null);

  async function run(inputs: RunInputs): Promise<void> {
    setSaid(null);
    const local: { said: Said | null } = { said: null };
    const result = await admission.submit({
      // Skipped while a request is held: that first request, session included, is resent.
      body: async () => {
        const field = profileField(inputs.profile);
        if (field === null) {
          local.said = CHOICE_REFUSED;
          return null;
        }
        let sessionId: string | null = null;
        if (inputs.expertId !== NO_EXPERT) {
          sessionId = await startSession(inputs.expertId);
          if (sessionId === null) {
            local.said = SESSION_FAILED;
            return null;
          }
        }
        return runBody(inputs, field, sessionId);
      },
      send: ({ key, body }) =>
        csrfFetch("/api/v1/runs", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": key,
          },
          body,
        }),
      parse: parseRunAccepted,
    });
    if (local.said !== null) {
      setSaid(local.said);
      return;
    }
    if (result === null || result.outcome === "changed") return;
    if (result.outcome === "accepted" && result.value !== null) onAccepted();
    setSaid(saidFor(result));
  }

  return {
    said,
    pending: admission.pending,
    held: admission.holding(),
    run,
  };
}
