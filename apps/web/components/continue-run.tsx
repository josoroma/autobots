"use client";

import { parseRunAccepted, type RunRequest } from "@autobots/api-client";
import { CircleAlert, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { AdmissionMessage } from "@/components/admission-message";
import { RunDisclosure } from "@/components/run-disclosure";
import { Button } from "@/components/ui/button";
import { csrfFetch } from "@/lib/csrf-fetch";
import { profileField } from "@/lib/model-profile";
import { admissionRefusal, CHOICE_NOT_OFFERED } from "@/lib/run-admission";
import { type Outcome, withHeld } from "@/lib/submit";
import { useSubmit } from "@/lib/use-submit";

const UNKNOWN =
  "The reply was lost, so it may have started. Running this again won't start a second one.";

// A finished run never reopens. This starts a new one linked to it, which is how failed work goes on.
export function ContinueRun({ runId }: { runId: string }) {
  const [open, setOpen] = useState(false);
  const [profile, setProfile] = useState("");
  const [started, setStarted] = useState<string | null>(null);
  const [problem, setProblem] = useState<{
    outcome: Outcome;
    text: string;
  } | null>(null);
  const [already, setAlready] = useState(false);
  // One key until the outcome is known, and one press at a time (Decision 0027 D2).
  const admission = useSubmit();
  // While a request is held, it's what gets resent, so its model stays as sent.
  const held = admission.holding();

  if (!open) {
    return (
      <Button variant="outline" onClick={() => setOpen(true)}>
        <RotateCcw aria-hidden="true" />
        Continue in a new run
      </Button>
    );
  }

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

  return (
    <div
      data-continue-run="true"
      className="bg-card space-y-3 rounded-xl border p-4 text-sm"
    >
      <p className="leading-relaxed">
        This starts a new run with the same goal, linked to this one, which
        stays as it is. Its steps are new, so it can repeat what this run did,
        and anything consequential waits for a new approval. Its Expert,
        session, input documents, required artifacts and criteria aren&apos;t
        carried over.
      </p>
      {started !== null ? null : held ? (
        <p className="text-muted-foreground">
          The model stays as chosen, as this may already be running.
        </p>
      ) : (
        <RunDisclosure chosen={profile} onChoose={setProfile} />
      )}
      {started === null ? (
        <Button disabled={admission.pending} onClick={() => void run()}>
          {admission.pending ? "Starting" : "Run"}
        </Button>
      ) : (
        <AdmissionMessage outcome="accepted">
          {already ? "It had already started. " : "Queued. "}
          <Link
            href={`/runs/${started}`}
            className="font-medium underline underline-offset-4"
          >
            {already ? "Open the run" : "Open the new run"}
          </Link>
        </AdmissionMessage>
      )}
      {problem === null ? null : (
        <AdmissionMessage
          outcome={problem.outcome}
          className="flex items-start gap-2"
        >
          <CircleAlert
            aria-hidden="true"
            className="text-destructive mt-0.5 size-4 shrink-0"
          />
          <span>{problem.text}</span>
        </AdmissionMessage>
      )}
    </div>
  );
}
