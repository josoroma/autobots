import { admitRun, type RunRequest } from "@autobots/api-client";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { writes } from "@/lib/api/browser";
import { profileField } from "@/lib/model-profile";
import { admissionRefusal, CHOICE_NOT_OFFERED } from "@/lib/run-admission";
import { type Attempt, type Outcome, withHeld } from "@/lib/submit";
import { useSubmit } from "@/lib/use-submit";

const UNKNOWN =
  "The reply was lost, so it may have started. Running this again won't start a second one.";

// One key until the outcome is known, so a lost reply never starts a second run (Decision 0027 D2).
function sendAdmission({ key, body }: Attempt<RunRequest>) {
  return admitRun(writes, body, { "Idempotency-Key": key });
}

export interface ContinueProblem {
  outcome: Outcome;
  text: string;
}

/**
 * Starts a new run linked to a finished one, which stays as it is. An accepted run renders the page
 * again on the server, so its server-read parts, such as the sidebar, include it (XWEB-14).
 */
export function useContinueRun(runId: string) {
  const router = useRouter();
  const [profile, setProfile] = useState("");
  const [started, setStarted] = useState<string | null>(null);
  const [problem, setProblem] = useState<ContinueProblem | null>(null);
  const [already, setAlready] = useState(false);
  // One key until the outcome is known, and one press at a time (Decision 0027 D2).
  const admission = useSubmit<RunRequest>();

  async function run(): Promise<void> {
    setProblem(null);
    const choice = { refused: false };
    const result = await admission.submit({
      body: () => {
        const field = profileField(profile);
        choice.refused = field === null;
        return field === null
          ? null
          : {
              // Left out on purpose: the server repeats the goal it stored, whole.
              continues_run_id: runId,
              ...field,
            };
      },
      send: sendAdmission,
    });
    if (choice.refused)
      setProblem({ outcome: "refused", text: CHOICE_NOT_OFFERED });
    if (result === null || result.outcome === "changed") return;
    if (result.outcome === "accepted" && result.value !== null) {
      setAlready(result.value.replayed);
      setStarted(result.value.run_id);
      router.refresh();
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
