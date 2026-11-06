"use client";

import {
  parseReconciliationResult,
  parseRunSummary,
} from "@autobots/api-client";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/field";
import { csrfFetch } from "@/lib/csrf-fetch";

type Command = "pause" | "resume" | "cancel";

const TERMINAL = new Set(["succeeded", "failed", "cancelled"]);
// SP-010: what each state can take. A terminal run takes nothing, so nothing is offered.
const PAUSABLE = new Set([
  "queued",
  "running",
  "waiting_input",
  "waiting_approval",
  "verifying",
]);
const LABELS: Record<Command, string> = {
  pause: "Pause",
  resume: "Resume",
  cancel: "Cancel run",
};
const MICRO_USD = 1_000_000;

export function commandsFor(status: string): Command[] {
  if (TERMINAL.has(status) || status === "cancelling") return [];
  if (status === "paused") return ["resume", "cancel"];
  return PAUSABLE.has(status) ? ["pause", "cancel"] : ["cancel"];
}

async function refusalOf(reply: Response | null): Promise<string> {
  const failure = (await reply?.json().catch(() => null)) as {
    message?: string;
  } | null;
  return failure?.message ?? "That could not be done. Nothing changed.";
}

export function RunControls({
  runId,
  status,
  version,
  openCalls,
  onChanged,
}: {
  runId: string;
  status: string;
  version: number;
  openCalls: number;
  onChanged: () => void;
}) {
  const [refusal, setRefusal] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [charge, setCharge] = useState("");
  const base = `/api/v1/runs/${encodeURIComponent(runId)}`;
  const commands = commandsFor(status);

  // A worker moves the version often, so each press reads the run's current one.
  async function currentVersion(): Promise<number> {
    const reply = await fetch(base, { cache: "no-store" }).catch(() => null);
    return reply?.ok === true
      ? parseRunSummary(await reply.json()).version
      : version;
  }

  async function send(command: Command): Promise<void> {
    setBusy(true);
    setRefusal(null);
    setNote(null);
    const reply = await csrfFetch(`${base}/${command}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": crypto.randomUUID(),
      },
      body: JSON.stringify({ expected_version: await currentVersion() }),
    }).catch(() => null);
    setBusy(false);
    if (reply?.ok !== true) setRefusal(await refusalOf(reply));
    onChanged();
  }

  async function reconcile(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setRefusal(null);
    setNote(null);
    const dollars = Number(charge);
    if (charge.trim() === "" || !Number.isFinite(dollars) || dollars < 0) {
      setRefusal("Enter the charge in US dollars, such as 0.0012.");
      return;
    }
    if (dollars > 0 && Math.round(dollars * MICRO_USD) === 0) {
      setRefusal(
        "That's under a millionth of a dollar, which can't be recorded. Enter 0 if there was no charge.",
      );
      return;
    }
    setBusy(true);
    const reply = await csrfFetch(`${base}/model-calls/reconcile`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": crypto.randomUUID(),
      },
      body: JSON.stringify({
        charged_micro_usd: Math.round(dollars * MICRO_USD),
      }),
    }).catch(() => null);
    setBusy(false);
    if (reply?.ok === true) {
      const result = parseReconciliationResult(await reply.json());
      if (result.reconciled_calls === 0) {
        setRefusal(
          "Nothing was recorded, as no call is waiting for a charge now. Your entry wasn't used.",
        );
      } else {
        setCharge("");
        setNote("The charge is recorded against the oldest open call.");
      }
    } else {
      setRefusal(await refusalOf(reply));
    }
    onChanged();
  }

  if (commands.length === 0 && openCalls === 0 && refusal === null) return null;
  return (
    <div data-run-controls="true" className="space-y-3">
      {commands.length === 0 ? null : (
        <div className="flex flex-wrap gap-2">
          {commands.map((command) => (
            <Button
              key={command}
              variant={command === "cancel" ? "secondary" : "default"}
              disabled={busy}
              onClick={() => void send(command)}
            >
              {LABELS[command]}
            </Button>
          ))}
        </div>
      )}
      {openCalls === 0 ? null : (
        <form
          onSubmit={(event) => void reconcile(event)}
          data-reconcile="true"
          className="space-y-2 text-sm"
        >
          <p>
            {openCalls === 1
              ? "One model call has"
              : `${openCalls} model calls have`}{" "}
            no settled charge. Look it up in OpenRouter&apos;s own records,
            since no one here can tell. Only the workspace owner can record it.
          </p>
          <label htmlFor="model-call-charge" className="font-medium">
            Charge seen, in US dollars
          </label>
          <Input
            id="model-call-charge"
            value={charge}
            onChange={(event) => setCharge(event.target.value)}
            inputMode="decimal"
            autoComplete="off"
          />
          <Button type="submit" variant="secondary" disabled={busy}>
            Record the charge
          </Button>
        </form>
      )}
      {refusal === null ? null : (
        <p role="alert" data-control-refusal="true" className="text-sm">
          {refusal}
        </p>
      )}
      {note === null ? null : (
        <p role="status" data-control-note="true" className="text-sm">
          {note}
        </p>
      )}
    </div>
  );
}
