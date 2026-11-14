"use client";

import {
  parseReconciliationResult,
  parseRunSummary,
} from "@autobots/api-client";
import { CircleAlert, CircleDollarSign, Pause, Play } from "lucide-react";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/field";
import { csrfFetch } from "@/lib/csrf-fetch";
import { readErrorResponse } from "@/lib/replies";

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
  const failure = await readErrorResponse(reply);
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
              variant={command === "cancel" ? "outline" : "default"}
              disabled={busy}
              onClick={() => void send(command)}
            >
              {command === "pause" ? (
                <Pause aria-hidden="true" />
              ) : command === "resume" ? (
                <Play aria-hidden="true" />
              ) : null}
              {LABELS[command]}
            </Button>
          ))}
        </div>
      )}
      {openCalls === 0 ? null : (
        <form
          onSubmit={(event) => void reconcile(event)}
          data-reconcile="true"
          className="border-attention/40 bg-card dark:bg-attention/5 space-y-3 rounded-xl border p-4 text-sm"
        >
          <p className="flex items-start gap-2.5 leading-relaxed">
            <CircleDollarSign
              aria-hidden="true"
              className="text-attention mt-0.5 size-4 shrink-0"
            />
            <span>
              {openCalls === 1
                ? "One model call has"
                : `${openCalls} model calls have`}{" "}
              no settled charge. Look it up in OpenRouter&apos;s own records,
              since no one here can tell. Only the workspace owner can record
              it.
            </span>
          </p>
          <div className="space-y-1.5">
            <label htmlFor="model-call-charge" className="block font-medium">
              Charge seen, in US dollars
            </label>
            <div className="flex flex-wrap items-center gap-2">
              <Input
                id="model-call-charge"
                value={charge}
                onChange={(event) => setCharge(event.target.value)}
                inputMode="decimal"
                autoComplete="off"
                className="w-40 font-mono tabular-nums"
              />
              <Button type="submit" variant="outline" disabled={busy}>
                Record the charge
              </Button>
            </div>
          </div>
        </form>
      )}
      {refusal === null ? null : (
        <p
          role="alert"
          data-control-refusal="true"
          className="flex items-start gap-2 text-sm"
        >
          <CircleAlert
            aria-hidden="true"
            className="text-destructive mt-0.5 size-4 shrink-0"
          />
          <span>{refusal}</span>
        </p>
      )}
      {note === null ? null : (
        <p
          role="status"
          data-control-note="true"
          className="text-muted-foreground text-sm"
        >
          {note}
        </p>
      )}
    </div>
  );
}
