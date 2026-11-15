import { type RunCommandRequest } from "@autobots/api-client";
import { useState } from "react";

import {
  COMMAND_LABEL,
  commandBody,
  commandTarget,
  sendRunCommand,
  type RunCommand,
} from "@/lib/runs/commands";
import { changedChoice, labelOf, withHeld } from "@/lib/submit";
import { useSubmit } from "@/lib/use-submit";

export const STALE =
  "This run changed after the panel loaded, so nothing was done. Reload the panel to see it now, then try again.";

/**
 * The runs list's panel sends the version it loaded, never a fresh one: a stale press is refused,
 * not retried (PRD-Studio RN-04). One key per press until its outcome is known (Decision 0027 D2),
 * so a lost reply applies it once. Pause and Resume share the run as their target, and Cancel has
 * its own (see commandTarget).
 */
export function usePanelCommands(runId: string, onAccepted: () => void) {
  const [refusal, setRefusal] = useState<string | null>(null);
  const writes = useSubmit<RunCommandRequest>();

  async function send(command: RunCommand, version: number): Promise<void> {
    setRefusal(null);
    const result = await writes.submit({
      body: () => commandBody(version),
      send: (attempt) => sendRunCommand(runId, command, attempt),
      scope: commandTarget(command),
      choice: command,
    });
    if (result === null) return;
    if (result.outcome === "changed") {
      setRefusal(changedChoice(labelOf(COMMAND_LABEL, result.heldChoice)));
      return;
    }
    if (result.outcome === "accepted") {
      onAccepted();
      return;
    }
    setRefusal(
      result.outcome === "unknown"
        ? "The reply was lost, so this may have applied. Pressing again won't apply it twice."
        : withHeld(
            result.refusal?.code === "version_conflict"
              ? STALE
              : (result.refusal?.message ??
                  "That could not be done. Nothing changed."),
            result.held,
          ),
    );
  }

  return {
    refusal,
    clear: () => setRefusal(null),
    busy: writes.pending,
    send,
  };
}
