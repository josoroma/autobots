/**
 * Turns a tool or a group on or off for the workspace (Decision 0033 W3 to W5). One write at a
 * time, each at the version the page last read. An accepted change reloads the catalog, so every
 * tool's availability and words follow it; any other says why and reloads too.
 */
import {
  putToolGroupSwitch,
  putToolSwitch,
  type ToolSwitchView,
} from "@autobots/api-client";
import { useState } from "react";

import { writes as writeClient } from "@/lib/api/browser";
import { SWITCH_SAVED } from "@/lib/tools/text";
import { refusalText } from "@/lib/submit";
import { useSubmit } from "@/lib/use-submit";

const REFUSALS: Readonly<Record<string, string>> = {
  stale_version:
    "The switches changed. They have been read again; try once more.",
  owner_required: "Only the workspace owner can turn tools on or off.",
  switch_not_found: "That tool or group has no switch.",
};
const LOST = "The switch couldn't be saved. Try again.";

export interface SwitchWrites {
  pending: boolean;
  /** The switch a write is pending for, as `tool:<id>` or `group:<id>`, or null. */
  saving: string | null;
  message: string | null;
  tool: (toolId: string, enabled: boolean, version: number) => Promise<void>;
  group: (group: string, enabled: boolean, version: number) => Promise<void>;
}

export function useSwitchWrites({
  reload,
}: {
  reload: () => void;
}): SwitchWrites {
  const writes = useSubmit<undefined>();
  const [message, setMessage] = useState<string | null>(null);
  const [target, setTarget] = useState<string | null>(null);

  async function send(
    name: string,
    request: () => Promise<ToolSwitchView>,
  ): Promise<void> {
    setMessage(null);
    setTarget(name);
    const result = await writes.submit({
      body: () => undefined,
      send: request,
      keyed: false,
    });
    if (result === null) return;
    const accepted = result.outcome === "accepted";
    setMessage(
      accepted ? SWITCH_SAVED : refusalText(REFUSALS, result.refusal, LOST),
    );
    reload();
  }

  return {
    pending: writes.pending,
    saving: writes.pending ? target : null,
    message,
    tool: (toolId, enabled, version) =>
      send(`tool:${toolId}`, () =>
        putToolSwitch(writeClient, toolId, {
          enabled,
          expected_version: version,
        }),
      ),
    group: (group, enabled, version) =>
      send(`group:${group}`, () =>
        putToolGroupSwitch(writeClient, group, {
          enabled,
          expected_version: version,
        }),
      ),
  };
}
