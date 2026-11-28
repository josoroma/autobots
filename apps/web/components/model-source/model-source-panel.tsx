"use client";

import {
  getModelSource,
  putModelSource,
  type ModelSourceState,
} from "@autobots/api-client";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Choice } from "@/components/ui/field";
import { LoadState } from "@/components/ui/load-state";
import { writes as writeClient } from "@/lib/api/browser";
import { readOf } from "@/lib/load";
import {
  matchedLine,
  profileLine,
  rolesLine,
  runtimeLine,
  SOURCE_CHOICES,
  SOURCE_REFUSALS,
  SPEND_NOTE,
  TOOLS_NOTE,
} from "@/lib/model-source";
import { refusalText } from "@/lib/submit";
import { useSettingsRead } from "@/lib/use-settings-read";
import { useSubmit } from "@/lib/use-submit";

const LOST = "Model source couldn't be saved. Reload and try again.";

// Decision 0041 A13: where every model call goes, above the provider panel and the model policy.
// Any member reads it; only the owner switches, at the version they saw (MP-05). `onSwitched`
// runs once a switch is accepted.
export function ModelSourcePanel({ onSwitched }: { onSwitched?: () => void }) {
  const read = useSettingsRead(readOf(getModelSource));
  const submit = useSubmit<undefined>();
  const [message, setMessage] = useState<string | null>(null);
  const state = read.value;
  if (state === null) {
    return (
      <LoadState
        state={read.state}
        what="Model source"
        onRetry={read.reload}
        pending={read.pending}
      />
    );
  }

  async function choose(
    source: ModelSourceState["source"],
    from: ModelSourceState,
  ) {
    if (source === from.source) return;
    setMessage(null);
    const result = await submit.submit({
      body: () => undefined,
      send: () =>
        putModelSource(writeClient, {
          expected_version: from.version,
          source,
        }),
      keyed: false,
    });
    if (result === null) return;
    if (result.outcome === "accepted" && result.value !== null) {
      read.adopt(result.value);
      setMessage(
        `Model source is now ${source === "local" ? "Local" : "OpenRouter"}.`,
      );
      onSwitched?.();
      return;
    }
    setMessage(refusalText(SOURCE_REFUSALS, result.refusal, LOST));
    read.reload();
  }

  return (
    <Card
      aria-labelledby="model-source-heading"
      data-panel="model-source"
      className="space-y-4 px-4 py-4"
    >
      <div className="flex items-center justify-between gap-3">
        <h2 id="model-source-heading" className="text-base font-semibold">
          Model source
        </h2>
        <Badge variant="outline">Owner only</Badge>
      </div>
      {message === null ? null : (
        <p role="status" aria-live="polite" className="text-sm font-medium">
          {message}
        </p>
      )}
      <fieldset className="space-y-2" disabled={submit.pending}>
        <legend className="sr-only">Where model calls go</legend>
        {SOURCE_CHOICES.map((choice) => (
          <label
            key={choice.value}
            data-source-choice={choice.value}
            className="flex items-start gap-2 text-sm"
          >
            <Choice
              name="model-source"
              value={choice.value}
              checked={state.source === choice.value}
              onChange={() => void choose(choice.value, state)}
              className="mt-1"
            />
            <span>
              <span className="font-medium">{choice.label}</span>{" "}
              <span className="text-muted-foreground">{choice.detail}</span>
            </span>
          </label>
        ))}
      </fieldset>
      <dl className="border-border grid gap-2 border-t pt-3 text-ui sm:grid-cols-[7rem_minmax(0,1fr)]">
        <dt className="text-muted-foreground">Local model</dt>
        <dd data-source-field="profiles">
          <ul className="space-y-1.5">
            {state.local_profiles.map((profile) => (
              <li key={profile.profile} data-local-profile={profile.profile}>
                <span className="font-medium">{profile.name}</span>{" "}
                <span className="text-muted-foreground">
                  {profileLine(profile)}
                </span>
                <span className="text-muted-foreground block text-xs">
                  {matchedLine(profile)}
                </span>
              </li>
            ))}
          </ul>
        </dd>
        <dt className="text-muted-foreground">Runtime</dt>
        <dd data-source-field="runtime">{runtimeLine(state.runtime)}</dd>
        <dt className="text-muted-foreground">Roles</dt>
        <dd data-source-field="roles">{rolesLine(state)}</dd>
        <dt className="text-muted-foreground">Spend</dt>
        <dd data-source-field="spend">
          {SPEND_NOTE}
          <span className="text-muted-foreground block">{TOOLS_NOTE}</span>
        </dd>
      </dl>
    </Card>
  );
}
