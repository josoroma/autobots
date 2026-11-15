import { Pause, Play } from "lucide-react";

import { Button } from "@/components/ui/button";
import { COMMAND_LABEL, type RunCommand } from "@/lib/runs/commands";

/**
 * The commands the service says a person may send this run now (RunWorkspace.allowed_commands),
 * one button each, shared by the run page and the runs list's panel (WRUN-12).
 */
export function RunCommandButtons({
  commands,
  busy,
  onSend,
}: {
  commands: readonly RunCommand[];
  busy: boolean;
  onSend: (command: RunCommand) => void;
}) {
  return commands.map((command) => (
    <Button
      key={command}
      variant={command === "cancel" ? "outline" : "default"}
      disabled={busy}
      onClick={() => onSend(command)}
    >
      {command === "pause" ? (
        <Pause aria-hidden="true" />
      ) : command === "resume" ? (
        <Play aria-hidden="true" />
      ) : null}
      {COMMAND_LABEL[command]}
    </Button>
  ));
}
