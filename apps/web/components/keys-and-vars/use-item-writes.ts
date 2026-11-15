/**
 * Saves and removes one key or var (PK-04 to PK-08, R-19). One write at a time. None sends a key,
 * and each replaces an item whole, so none is held. `saving` names the item being written, so only
 * its card says Saving (WSYS-14). An accepted reply is shown; any other says why and reads again.
 */
import {
  deleteKeyOrVar,
  putKeyOrVar,
  type KeysAndVars,
} from "@autobots/api-client";
import { useState } from "react";

import { writes as writeClient } from "@/lib/api/browser";
import {
  ITEM_REMOVED,
  ITEM_SAVED,
  itemActionText,
  type Name,
} from "@/lib/keys-and-vars";
import { useSubmit } from "@/lib/use-submit";

export interface ItemWrites {
  pending: boolean;
  /** The item a write is pending for, or null. */
  saving: Name | null;
  message: string | null;
  /** A secret's value goes straight into the request's body; it's never kept in state. */
  save: (name: Name, value: string, version: number) => Promise<void>;
  remove: (name: Name, version: number) => Promise<void>;
}

export function useItemWrites({
  adopt,
  reload,
}: {
  adopt: (next: KeysAndVars) => void;
  reload: () => void;
}): ItemWrites {
  // Each press builds its own request and nothing is held (keyed: false), so the hook carries no
  // body.
  const writes = useSubmit<undefined>();
  const [message, setMessage] = useState<string | null>(null);
  const [target, setTarget] = useState<Name | null>(null);

  async function send(
    name: Name,
    request: () => Promise<KeysAndVars>,
    done: string,
  ): Promise<void> {
    setMessage(null);
    setTarget(name);
    const result = await writes.submit({
      body: () => undefined,
      send: request,
      keyed: false,
    });
    if (result === null) return;
    const value = result.outcome === "accepted" ? result.value : null;
    if (value !== null) adopt(value);
    setMessage(itemActionText(value !== null, result.refusal, done));
    if (value === null) reload();
  }

  return {
    pending: writes.pending,
    saving: writes.pending ? target : null,
    message,
    save: (name, value, version) =>
      send(
        name,
        () =>
          putKeyOrVar(writeClient, name, { value, expected_version: version }),
        ITEM_SAVED,
      ),
    remove: (name, version) =>
      send(
        name,
        () => deleteKeyOrVar(writeClient, name, { expected_version: version }),
        ITEM_REMOVED,
      ),
  };
}
