"use client";

import { parseKeysAndVars, type KeyOrVar } from "@autobots/api-client";

import { ItemCard } from "@/components/keys-and-vars/item-card";
import { useItemWrites } from "@/components/keys-and-vars/use-item-writes";
import { LoadState } from "@/components/ui/load-state";
import { useSettingsRead } from "@/lib/use-settings-read";

// Decisions 0024 and 0025, PRD-Tool-Catalog PK-04 to PK-08: the workspace's keys and vars, each
// saved here over the environment and .env, from the next tool call, with no restart.
export function KeysAndVarsPanel() {
  const read = useSettingsRead("/api/settings/keys-and-vars", parseKeysAndVars);
  const writes = useItemWrites(read);
  const items = read.value;
  if (items === null) {
    return (
      <LoadState
        state={read.state}
        what="keys and vars"
        onRetry={read.reload}
        pending={read.pending}
      />
    );
  }
  const card = (item: KeyOrVar) => (
    <ItemCard
      key={item.name}
      item={item}
      busy={writes.pending}
      saving={writes.saving === item.name}
      onSave={(value) => void writes.save(item.name, value, item.version)}
      onRemove={() => void writes.remove(item.name, item.version)}
    />
  );
  return (
    <div className="space-y-6">
      <p className="text-muted-foreground max-w-2xl text-[13px] leading-relaxed">
        A key or value saved here is used for this workspace instead of the
        server environment and .env, from the next tool call, with no restart.
        Saving checks a key&apos;s format only and calls no provider. Only the
        workspace owner can save or remove one.
      </p>
      {writes.message === null ? null : (
        <p role="status" aria-live="polite" className="text-sm font-medium">
          {writes.message}
        </p>
      )}
      <section aria-labelledby="keys-heading" className="space-y-4">
        <h2 id="keys-heading" className="text-sm font-semibold">
          Keys
        </h2>
        {items.items.filter((item) => item.kind === "secret").map(card)}
      </section>
      <section aria-labelledby="vars-heading" className="space-y-4">
        <h2 id="vars-heading" className="text-sm font-semibold">
          Vars
        </h2>
        {items.items.filter((item) => item.kind === "value").map(card)}
      </section>
    </div>
  );
}
