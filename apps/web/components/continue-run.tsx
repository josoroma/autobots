"use client";

import Link from "next/link";
import { useRef, useState } from "react";

import { RunDisclosure } from "@/components/run-disclosure";
import { Button } from "@/components/ui/button";
import { csrfFetch } from "@/lib/csrf-fetch";

// A finished run never reopens. This starts a new one linked to it, which is how failed work goes on.
export function ContinueRun({ runId }: { runId: string }) {
  const [open, setOpen] = useState(false);
  const [profile, setProfile] = useState("");
  const [started, setStarted] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [lost, setLost] = useState(false);
  const [already, setAlready] = useState(false);
  // Kept until the outcome is known, so pressing again after a lost reply starts nothing new.
  const key = useRef<string | null>(null);

  if (!open) {
    return (
      <Button variant="secondary" onClick={() => setOpen(true)}>
        Continue in a new run
      </Button>
    );
  }

  async function run(): Promise<void> {
    setProblem(null);
    setPending(true);
    const reply = await csrfFetch("/api/v1/runs", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": (key.current ??= crypto.randomUUID()),
      },
      body: JSON.stringify({
        // Left out on purpose: the server repeats the goal it stored, whole.
        continues_run_id: runId,
        ...(profile === "" ? {} : { run_profile: profile }),
      }),
    }).catch(() => null);
    // A 5xx can come after the API committed, so it proves no more than a lost reply.
    if (reply === null || reply.status >= 500) {
      unknownOutcome();
      return;
    }
    if (reply.ok) {
      const accepted = (await reply.json().catch(() => null)) as {
        run_id: string;
        replayed?: boolean;
      } | null;
      if (accepted === null) {
        unknownOutcome();
        return;
      }
      setAlready(accepted.replayed === true);
      setStarted(accepted.run_id);
      return;
    }
    const failure = (await reply.json().catch(() => null)) as {
      message?: string;
    } | null;
    // Only a refusal with no earlier unknown attempt proves nothing started under this key.
    if (!lost) key.current = null;
    setPending(false);
    setProblem(failure?.message ?? "That could not be started.");
  }

  function unknownOutcome(): void {
    setLost(true);
    setPending(false);
    setProblem(
      "The reply was lost, so it may have started. Running this again won't start a second one.",
    );
  }

  return (
    <div data-continue-run="true" className="space-y-2 text-sm">
      <p>
        This starts a new run with the same goal, linked to this one, which
        stays as it is. Its steps are new, so it can repeat what this run did,
        and anything consequential waits for a new approval. Its Expert,
        session, input documents, required artifacts and criteria aren&apos;t
        carried over.
      </p>
      {lost ? (
        <p>The model stays as chosen, as this may already be running.</p>
      ) : (
        <RunDisclosure chosen={profile} onChoose={setProfile} />
      )}
      {started === null ? (
        <Button disabled={pending} onClick={() => void run()}>
          {pending ? "Starting" : "Run"}
        </Button>
      ) : (
        <p role="status">
          {already ? "It had already started. " : "Queued. "}
          <Link href={`/runs/${started}`} className="font-medium underline">
            {already ? "Open the run" : "Open the new run"}
          </Link>
        </p>
      )}
      {problem === null ? null : <p role="alert">{problem}</p>}
    </div>
  );
}
