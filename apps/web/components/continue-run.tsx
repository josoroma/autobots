"use client";

import { parseRunAccepted, type RunRequest } from "@autobots/api-client";
import { CircleAlert, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { RunDisclosure } from "@/components/run-disclosure";
import { Button } from "@/components/ui/button";
import { csrfFetch } from "@/lib/csrf-fetch";
import { profileField } from "@/lib/model-profile";
import { useSubmit } from "@/lib/use-submit";

// A finished run never reopens. This starts a new one linked to it, which is how failed work goes on.
export function ContinueRun({ runId }: { runId: string }) {
  const [open, setOpen] = useState(false);
  const [profile, setProfile] = useState("");
  const [started, setStarted] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [already, setAlready] = useState(false);
  // While the outcome is unknown, the first request is what gets resent, so its model stays.
  const [lost, setLost] = useState(false);
  // One key until the outcome is known, and one press at a time (Decision 0027 D2).
  const admission = useSubmit();

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
    const result = await admission.submit({
      body: () =>
        JSON.stringify({
          // Left out on purpose: the server repeats the goal it stored, whole.
          continues_run_id: runId,
          ...profileField(profile),
        } satisfies RunRequest),
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
    if (result === null) return;
    setLost(result.outcome === "unknown");
    if (result.outcome === "accepted" && result.value !== null) {
      setAlready(result.value.replayed);
      setStarted(result.value.run_id);
      return;
    }
    setProblem(
      result.outcome === "unknown"
        ? "The reply was lost, so it may have started. Running this again won't start a second one."
        : (result.refusal?.message ?? "That could not be started."),
    );
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
      {started !== null ? null : lost ? (
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
        <p role="status">
          {already ? "It had already started. " : "Queued. "}
          <Link
            href={`/runs/${started}`}
            className="font-medium underline underline-offset-4"
          >
            {already ? "Open the run" : "Open the new run"}
          </Link>
        </p>
      )}
      {problem === null ? null : (
        <p role="alert" className="flex items-start gap-2">
          <CircleAlert
            aria-hidden="true"
            className="text-destructive mt-0.5 size-4 shrink-0"
          />
          <span>{problem}</span>
        </p>
      )}
    </div>
  );
}
