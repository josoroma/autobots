import { parseRunAccepted, type RunRequest } from "@autobots/api-client";
import { useState } from "react";

import { csrfFetch } from "@/lib/csrf-fetch";
import { profileField } from "@/lib/model-profile";
import { admissionRefusal, CHOICE_NOT_OFFERED } from "@/lib/run-admission";
import { type Attempt, type Outcome, withHeld } from "@/lib/submit";
import { useSubmit } from "@/lib/use-submit";

const UNKNOWN =
  "The reply was lost, so it may have started. Running this again won't start a second one.";

// One key until the outcome is known, so a lost reply never starts a second run (Decision 0027 D2).
function sendAdmission({ key, body }: Attempt): Promise<Response> {
  return csrfFetch("/api/v1/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json", "Idempotency-Key": key },
    body,
  });
}

export interface ContinueProblem {
  outcome: Outcome;
  text: string;
}

/** Starts a new run linked to a finished one, which stays as it is. */
export function useContinueRun(runId: string) {
  const [profile, setProfile] = useState("");
  const [started, setStarted] = useState<string | null>(null);
  const [problem, setProblem] = useState<ContinueProblem | null>(null);
  const [already, setAlready] = useState(false);
  // One key until the outcome is known, and one press at a time (Decision 0027 D2).
  const admission = useSubmit();

  async function run(): Promise<void> {
    setProblem(null);
    const choice = { refused: false };
    const result = await admission.submit({
      body: () => {
        const field = profileField(profile);
        choice.refused = field === null;
        return field === null
          ? null
          : JSON.stringify({
              // Left out on purpose: the server repeats the goal it stored, whole.
              continues_run_id: runId,
              ...field,
            } satisfies RunRequest);
      },
      send: sendAdmission,
      parse: parseRunAccepted,
    });
    if (choice.refused)
      setProblem({ outcome: "refused", text: CHOICE_NOT_OFFERED });
    if (result === null || result.outcome === "changed") return;
    if (result.outcome === "accepted" && result.value !== null) {
      setAlready(result.value.replayed);
      setStarted(result.value.run_id);
      return;
    }
    setProblem({
      outcome: result.outcome,
      text:
        result.outcome === "unknown"
          ? UNKNOWN
          : withHeld(
              admissionRefusal(result.refusal, result.status),
              result.held,
            ),
    });
  }

  return {
    profile,
    setProfile,
    started,
    already,
    problem,
    pending: admission.pending,
    // While a request is held, it's what gets resent, so its model stays as sent.
    held: admission.holding(),
    run,
  };
}
