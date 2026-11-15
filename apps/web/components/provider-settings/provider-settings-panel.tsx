"use client";

import { getModelProviders } from "@autobots/api-client";

import { ConnectionBar } from "@/components/provider-settings/connection-bar";
import { KeyActions } from "@/components/provider-settings/key-actions";
import {
  EnvironmentKeyNote,
  KeyForm,
} from "@/components/provider-settings/key-form";
import { RouteQualifications } from "@/components/provider-settings/route-qualifications";
import { useProviderWrites } from "@/components/provider-settings/use-provider-writes";
import { Card } from "@/components/ui/card";
import { LoadState } from "@/components/ui/load-state";
import { readOf } from "@/lib/load";
import { useSettingsRead } from "@/lib/use-settings-read";

// PRD-Model-Providers: the OpenRouter key's source and status, its field and actions, and each
// route's live qualification. Saving checks the key's metadata only and starts no model call.
export function ProviderSettingsPanel() {
  const read = useSettingsRead(readOf(getModelProviders));
  const writes = useProviderWrites(read);
  const status = read.value;
  if (status === null) {
    return (
      <LoadState
        state={read.state}
        what="provider settings"
        onRetry={read.reload}
        pending={read.pending}
      />
    );
  }
  const version = status.settings_version;
  return (
    <>
      <Card
        aria-labelledby="openrouter-heading"
        className="overflow-hidden p-0"
      >
        <ConnectionBar status={status} />
        <div className="border-border space-y-4 border-t px-[18px] py-4">
          {writes.message === null ? null : (
            <p role="status" aria-live="polite" className="text-sm font-medium">
              {writes.message}
            </p>
          )}
          {status.source === "environment" ? (
            <EnvironmentKeyNote />
          ) : (
            <KeyForm
              replacing={status.source === "app"}
              pending={writes.pending}
              onSubmit={(draft) => void writes.saveKey(draft, version)}
            />
          )}
          <KeyActions
            source={status.source}
            pending={writes.pending}
            onValidate={() => void writes.validate()}
            onDisconnect={() => void writes.disconnect(version)}
          />
        </div>
      </Card>
      <RouteQualifications routes={status.qualification} />
    </>
  );
}
