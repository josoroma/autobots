"use client";

import {
  getBrowsingSettings,
  putBrowsingSettings,
  type BrowsingSettingsView,
} from "@autobots/api-client";
import { useState } from "react";

import { Choice } from "@/components/ui/field";
import { LoadState } from "@/components/ui/load-state";
import { writes as writeClient } from "@/lib/api/browser";
import { readOf } from "@/lib/load";
import { refusalText } from "@/lib/submit";
import { useSettingsRead } from "@/lib/use-settings-read";
import { useSubmit } from "@/lib/use-submit";

const REFUSALS: Readonly<Record<string, string>> = {
  stale_version: "The setting changed. It has been read again; try once more.",
  owner_required: "Only the workspace owner can change this setting.",
};
const LOST = "The setting couldn't be saved. Try again.";

// Decision 0035 Y1 to Y4: whether a browse may start without asking and type and submit, within
// the browse domains each Expert lists. Every member reads it; only the owner changes it.
export function BrowsingPanel() {
  const read = useSettingsRead(readOf(getBrowsingSettings));
  const writes = useSubmit<undefined>();
  const [message, setMessage] = useState<string | null>(null);
  // The choice shows at once while it saves, then the saved value, whatever came back.
  const [chosen, setChosen] = useState<boolean | null>(null);
  const setting = read.value;
  if (setting === null) {
    return (
      <LoadState
        state={read.state}
        what="the browsing setting"
        onRetry={read.reload}
        pending={read.pending}
      />
    );
  }

  async function save(current: BrowsingSettingsView, yolo: boolean) {
    setMessage(null);
    setChosen(yolo);
    const result = await writes.submit({
      body: () => undefined,
      send: () =>
        putBrowsingSettings(writeClient, {
          yolo,
          expected_version: current.version,
        }),
      keyed: false,
    });
    setChosen(null);
    if (result === null) return;
    if (result.outcome === "accepted" && result.value !== null) {
      read.adopt(result.value);
      setMessage(yolo ? "YOLO is on." : "YOLO is off.");
      return;
    }
    setMessage(refusalText(REFUSALS, result.refusal, LOST));
    read.reload();
  }

  return (
    <fieldset className="min-w-0 space-y-2.5" data-field="browsing-yolo">
      <legend className="mb-1 text-sm font-semibold">Browsing</legend>
      <label className="border-border has-checked:border-primary/65 flex max-w-lg cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-ui has-disabled:cursor-default">
        <Choice
          type="checkbox"
          checked={chosen ?? setting.yolo}
          disabled={!setting.viewer_can_change || writes.pending}
          onChange={(event) => void save(setting, event.target.checked)}
        />
        Let browsing type and submit (YOLO)
      </label>
      <p className="text-muted-foreground max-w-lg text-meta leading-relaxed">
        While this is on, a browse starts without asking you, and goes only to
        the domains its Expert lists. While it is off, a person approves every
        browse, and browsing only reads. Turning it off applies at once; turning
        it on applies to runs started after.
      </p>
      {setting.viewer_can_change ? null : (
        <p className="text-muted-foreground max-w-lg text-meta leading-relaxed">
          Only the workspace owner can change this setting.
        </p>
      )}
      {message === null ? null : (
        <p role="status" aria-live="polite" className="text-sm font-medium">
          {message}
        </p>
      )}
    </fieldset>
  );
}
