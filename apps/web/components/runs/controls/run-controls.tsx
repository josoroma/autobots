"use client";

import { CircleAlert } from "lucide-react";

import { ChargeForm } from "@/components/runs/controls/charge-form";
import { useRunControls } from "@/components/runs/controls/use-run-controls";
import { RunCommandButtons } from "@/components/runs/run-command-buttons";
import type { RunCommand } from "@/lib/runs/commands";

/**
 * The run page's controls: the commands the service offers this run now, and the charge entry
 * while a model call's charge is unsettled.
 */
export function RunControls({
  runId,
  commands,
  version,
  openCalls,
  onChanged,
}: {
  runId: string;
  commands: readonly RunCommand[];
  version: number;
  openCalls: number;
  onChanged: () => void;
}) {
  const controls = useRunControls(runId, version, onChanged);
  if (commands.length === 0 && openCalls === 0 && controls.refusal === null)
    return null;
  return (
    <div data-run-controls="true" className="space-y-3">
      {commands.length === 0 ? null : (
        <div className="flex flex-wrap gap-2">
          <RunCommandButtons
            commands={commands}
            busy={controls.busy}
            onSend={(command) => void controls.send(command)}
          />
        </div>
      )}
      {openCalls === 0 ? null : (
        <ChargeForm
          openCalls={openCalls}
          charge={controls.charge}
          busy={controls.busy}
        />
      )}
      {controls.refusal === null ? null : (
        <p
          role="alert"
          data-control-refusal="true"
          className="flex items-start gap-2 text-sm"
        >
          <CircleAlert
            aria-hidden="true"
            className="text-destructive mt-0.5 size-4 shrink-0"
          />
          <span>{controls.refusal}</span>
        </p>
      )}
      {controls.note === null ? null : (
        <p
          role="status"
          data-control-note="true"
          className="text-muted-foreground text-sm"
        >
          {controls.note}
        </p>
      )}
    </div>
  );
}
