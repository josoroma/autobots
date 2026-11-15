/**
 * The OpenRouter key's actions: save and validate, validate, and disconnect (PRD-Model-Providers,
 * R-19). One write at a time. None sends a key, and each replaces the status whole, so none is
 * held. An accepted reply becomes the status; any other says why and reads the status again.
 */
import {
  deleteOpenRouterCredential,
  putOpenRouterCredential,
  validateOpenRouter,
  type ProviderStatus,
} from "@autobots/api-client";
import { useState } from "react";

import { writes as writeClient } from "@/lib/api/browser";
import {
  KEY_DISCONNECTED,
  KEY_SAVED,
  KEY_VALIDATED,
  keyActionText,
} from "@/lib/provider-text";
import { useSubmit } from "@/lib/use-submit";

export interface ProviderWrites {
  pending: boolean;
  /** What the newest action said, or null. */
  message: string | null;
  /** The draft key goes straight into the request's body; it's never kept in state. */
  saveKey: (draft: string, version: number) => Promise<void>;
  validate: () => Promise<void>;
  disconnect: (version: number) => Promise<void>;
}

export function useProviderWrites({
  adopt,
  reload,
}: {
  adopt: (next: ProviderStatus) => void;
  reload: () => void;
}): ProviderWrites {
  // Each press builds its own request and nothing is held (keyed: false), so the hook carries no
  // body.
  const writes = useSubmit<undefined>();
  const [message, setMessage] = useState<string | null>(null);

  async function send(
    request: () => Promise<ProviderStatus>,
    done: string,
  ): Promise<void> {
    setMessage(null);
    const result = await writes.submit({
      body: () => undefined,
      send: request,
      keyed: false,
    });
    if (result === null) return;
    const value = result.outcome === "accepted" ? result.value : null;
    if (value !== null) adopt(value);
    setMessage(keyActionText(value !== null, result.refusal, done));
    if (value === null) reload();
  }

  return {
    pending: writes.pending,
    message,
    saveKey: (draft, version) =>
      send(
        () =>
          putOpenRouterCredential(writeClient, {
            draft_key: draft,
            expected_version: version,
          }),
        KEY_SAVED,
      ),
    validate: () => send(() => validateOpenRouter(writeClient), KEY_VALIDATED),
    disconnect: (version) =>
      send(
        () =>
          deleteOpenRouterCredential(writeClient, {
            expected_version: version,
          }),
        KEY_DISCONNECTED,
      ),
  };
}
