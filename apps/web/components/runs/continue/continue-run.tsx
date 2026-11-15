"use client";

import { CircleAlert, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { AdmissionMessage } from "@/components/admission-message";
import { useContinueRun } from "@/components/runs/continue/use-continue-run";
import { RunDisclosure } from "@/components/runs/disclosure/run-disclosure";
import { Button } from "@/components/ui/button";

// A finished run never reopens. This starts a new one linked to it, which is how failed work goes on.
export function ContinueRun({ runId }: { runId: string }) {
  const [open, setOpen] = useState(false);
  const flow = useContinueRun(runId);
  if (!open) {
    return (
      <Button variant="outline" onClick={() => setOpen(true)}>
        <RotateCcw aria-hidden="true" />
        Continue in a new run
      </Button>
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
      {flow.started !== null ? null : flow.held ? (
        <p className="text-muted-foreground">
          The model stays as chosen, as this may already be running.
        </p>
      ) : (
        <RunDisclosure chosen={flow.profile} onChoose={flow.setProfile} />
      )}
      {flow.started === null ? (
        <Button disabled={flow.pending} onClick={() => void flow.run()}>
          {flow.pending ? "Starting" : "Run"}
        </Button>
      ) : (
        <AdmissionMessage outcome="accepted">
          {flow.already ? "It had already started. " : "Queued. "}
          <Link
            href={`/runs/${flow.started}`}
            className="font-medium underline underline-offset-4"
          >
            {flow.already ? "Open the run" : "Open the new run"}
          </Link>
        </AdmissionMessage>
      )}
      {flow.problem === null ? null : (
        <AdmissionMessage
          outcome={flow.problem.outcome}
          className="flex items-start gap-2"
        >
          <CircleAlert
            aria-hidden="true"
            className="text-destructive mt-0.5 size-4 shrink-0"
          />
          <span>{flow.problem.text}</span>
        </AdmissionMessage>
      )}
    </div>
  );
}
