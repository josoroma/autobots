/**
 * The run page's commands and charge entry (WRUN-05). The two flows share one refusal and one note,
 * so a press of either replaces what the other said, and one busy flag, so neither sends while the
 * other is pending.
 */
import {
  reconcileRunModelCalls,
  type ErrorResponse,
  type ModelCallReconciliation,
  type RunCommandRequest,
} from "@autobots/api-client";
import { useState, type FormEvent } from "react";

import { writes as writeClient } from "@/lib/api/browser";
import { chargeEntry } from "@/lib/runs/charges";
import {
  COMMAND_LABEL,
  commandBody,
  commandTarget,
  currentVersion,
  sendRunCommand,
  type RunCommand,
} from "@/lib/runs/commands";
import { changedChoice, labelOf, withHeld } from "@/lib/submit";
import { useSubmit } from "@/lib/use-submit";

function refusalOf(failure: ErrorResponse | null): string {
  return failure?.message ?? "That could not be done. Nothing changed.";
}

const UNKNOWN =
  "This may have been recorded. The reply was lost, so pressing again won't record it twice.";

export interface ControlMessages {
  refusal: string | null;
  note: string | null;
}

const QUIET: ControlMessages = { refusal: null, note: null };
const refuse = (refusal: string): ControlMessages => ({ refusal, note: null });
type Say = (messages: ControlMessages) => void;

export function useRunControls(
  runId: string,
  version: number,
  onChanged: () => void,
) {
  const [messages, say] = useState<ControlMessages>(QUIET);
  const commands = useCommandWrites(runId, version, onChanged, say);
  const charge = useChargeWrites(runId, onChanged, say);
  const busy = commands.pending || charge.pending;
  return { ...messages, busy, send: commands.send, charge };
}

// One key per press until its outcome is known (Decision 0027 D2): a lost reply resends the same
// request, so a command applies once (WRUN-03). Pause and Resume share the run as their target, so
// after a lost Pause, Resume sends nothing until a reload shows whether it applied. Cancel has its
// own: a repeated cancellation changes nothing, so it can't contradict either, and a lost Pause
// never holds back stopping the run.
function useCommandWrites(
  runId: string,
  version: number,
  onChanged: () => void,
  say: Say,
) {
  const writes = useSubmit<RunCommandRequest>();
  async function send(command: RunCommand): Promise<void> {
    say(QUIET);
    const result = await writes.submit({
      // A worker moves the version often, so each press reads the run's current one.
      body: async () => commandBody(await currentVersion(runId, version)),
      send: (attempt) => sendRunCommand(runId, command, attempt),
      scope: commandTarget(command),
      choice: command,
    });
    if (result === null) return;
    if (result.outcome === "changed") {
      say(refuse(changedChoice(labelOf(COMMAND_LABEL, result.heldChoice))));
      return;
    }
    if (result.outcome === "unknown") say(refuse(UNKNOWN));
    else if (result.outcome === "refused")
      say(refuse(withHeld(refusalOf(result.refusal), result.held)));
    onChanged();
  }
  return { pending: writes.pending, send };
}

export interface ChargeWrites {
  pending: boolean;
  /** While a charge is held, its amount stays as sent (Decision 0027 D2). */
  held: boolean;
  value: string;
  setValue: (value: string) => void;
  reconcile: (event: FormEvent<HTMLFormElement>) => Promise<void>;
}

// One key per entry until its outcome is known, so a charge is never recorded twice (WRUN-03).
function useChargeWrites(
  runId: string,
  onChanged: () => void,
  say: Say,
): ChargeWrites {
  const writes = useSubmit<ModelCallReconciliation>();
  const [value, setValue] = useState("");
  async function reconcile(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    say(QUIET);
    const result = await writes.submit({
      body: () => {
        const entry = chargeEntry(value);
        if ("problem" in entry) {
          say(refuse(entry.problem));
          return null;
        }
        return { charged_micro_usd: entry.micro };
      },
      send: ({ key, body }) =>
        reconcileRunModelCalls(writeClient, runId, body, {
          "Idempotency-Key": key,
        }),
    });
    if (result === null) return;
    if (result.outcome === "accepted" && result.value !== null) {
      if (result.value.reconciled_calls === 0) {
        say(
          refuse(
            "Nothing was recorded, as no call is waiting for a charge now. Your entry wasn't used.",
          ),
        );
      } else {
        setValue("");
        say({
          refusal: null,
          note: "The charge is recorded against the oldest open call.",
        });
      }
    } else if (result.outcome === "unknown") {
      say(refuse(UNKNOWN));
    } else {
      say(refuse(withHeld(refusalOf(result.refusal), result.held)));
    }
    onChanged();
  }
  return {
    pending: writes.pending,
    held: writes.holding(),
    value,
    setValue,
    reconcile,
  };
}
