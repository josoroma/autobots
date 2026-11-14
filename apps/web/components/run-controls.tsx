"use client";

import {
  type ErrorResponse,
  parseReconciliationResult,
  parseRunCommandResult,
  parseRunSummary,
  type RunStatus,
} from "@autobots/api-client";
import { CircleAlert, CircleDollarSign, Pause, Play } from "lucide-react";
import { useState, type FormEvent } from "react";

import { HeldNote } from "@/components/held-note";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/field";
import { csrfFetch } from "@/lib/csrf-fetch";
import { MICRO_USD } from "@/lib/format";
import {
  COMMAND_LABEL,
  commandTarget,
  commandsFor,
  type RunCommand,
} from "@/lib/runs/status";
import { changedChoice, labelOf, withHeld } from "@/lib/submit";
import { useSubmit } from "@/lib/use-submit";

function refusalOf(failure: ErrorResponse | null): string {
  return failure?.message ?? "That could not be done. Nothing changed.";
}

const UNKNOWN =
  "This may have been recorded. The reply was lost, so pressing again won't record it twice.";

export function RunControls({
  runId,
  status,
  version,
  openCalls,
  onChanged,
}: {
  runId: string;
  status: RunStatus;
  version: number;
  openCalls: number;
  onChanged: () => void;
}) {
  const [refusal, setRefusal] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const commandWrites = useSubmit();
  const charges = useSubmit();
  const busy = commandWrites.pending || charges.pending;
  // While a charge is held, its amount stays as sent (Decision 0027 D2).
  const chargeHeld = charges.holding();
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

  // One key per press until its outcome is known (Decision 0027 D2): a lost reply resends the
  // same request, so a command applies once and a charge is never recorded twice (WRUN-03). Pause
  // and Resume share the run as their target, so after a lost Pause, Resume sends nothing until a
  // reload shows whether it applied. Cancel has its own: a repeated cancellation changes nothing, so
  // it can't contradict either, and a lost Pause never holds back stopping the run.
  async function send(command: RunCommand): Promise<void> {
    setRefusal(null);
    setNote(null);
    const result = await commandWrites.submit({
      body: async () =>
        JSON.stringify({ expected_version: await currentVersion() }),
      send: ({ key, body }) =>
        csrfFetch(`${base}/${command}`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": key,
          },
          body,
        }),
      parse: parseRunCommandResult,
      scope: commandTarget(command),
      choice: command,
    });
    if (result === null) return;
    if (result.outcome === "changed") {
      setRefusal(changedChoice(labelOf(COMMAND_LABEL, result.heldChoice)));
      return;
    }
    if (result.outcome === "unknown") setRefusal(UNKNOWN);
    else if (result.outcome === "refused")
      setRefusal(withHeld(refusalOf(result.refusal), result.held));
    onChanged();
  }

  async function reconcile(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setRefusal(null);
    setNote(null);
    const result = await charges.submit({
      body: () => {
        const dollars = Number(charge);
        if (charge.trim() === "" || !Number.isFinite(dollars) || dollars < 0) {
          setRefusal("Enter the charge in US dollars, such as 0.0012.");
          return null;
        }
        if (dollars > 0 && Math.round(dollars * MICRO_USD) === 0) {
          setRefusal(
            "That's under a millionth of a dollar, which can't be recorded. Enter 0 if there was no charge.",
          );
          return null;
        }
        return JSON.stringify({
          charged_micro_usd: Math.round(dollars * MICRO_USD),
        });
      },
      send: ({ key, body }) =>
        csrfFetch(`${base}/model-calls/reconcile`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": key,
          },
          body,
        }),
      parse: parseReconciliationResult,
    });
    if (result === null) return;
    if (result.outcome === "accepted" && result.value !== null) {
      if (result.value.reconciled_calls === 0) {
        setRefusal(
          "Nothing was recorded, as no call is waiting for a charge now. Your entry wasn't used.",
        );
      } else {
        setCharge("");
        setNote("The charge is recorded against the oldest open call.");
      }
    } else if (result.outcome === "unknown") {
      setRefusal(UNKNOWN);
    } else {
      setRefusal(withHeld(refusalOf(result.refusal), result.held));
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
              {COMMAND_LABEL[command]}
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
                readOnly={chargeHeld}
                onChange={(event) => setCharge(event.target.value)}
                inputMode="decimal"
                autoComplete="off"
                className="w-40 font-mono tabular-nums"
              />
              <Button type="submit" variant="outline" disabled={busy}>
                Record the charge
              </Button>
            </div>
            {chargeHeld ? <HeldNote /> : null}
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
