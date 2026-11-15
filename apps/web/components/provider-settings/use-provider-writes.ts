/**
 * The OpenRouter key's actions: save and validate, validate, and disconnect (PRD-Model-Providers,
 * R-19). One write at a time. None sends a key, and each replaces the status whole, so none is
 * held. An accepted reply becomes the status; any other says why and reads the status again.
 */
import { parseProviderStatus, type ProviderStatus } from "@autobots/api-client";
import { useState } from "react";

import { csrfFetch } from "@/lib/csrf-fetch";
import {
  KEY_DISCONNECTED,
  KEY_SAVED,
  KEY_VALIDATED,
  keyActionText,
} from "@/lib/provider-text";
import { useSubmit } from "@/lib/use-submit";

const CREDENTIAL = "/api/settings/model-providers/openrouter/credential";
const VALIDATE = "/api/settings/model-providers/openrouter/validate";

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
  const writes = useSubmit();
  const [message, setMessage] = useState<string | null>(null);

  async function send(
    path: string,
    method: "PUT" | "POST" | "DELETE",
    body: unknown,
    done: string,
  ): Promise<void> {
    setMessage(null);
    const result = await writes.submit({
      body: () => (body === undefined ? "" : JSON.stringify(body)),
      send: ({ body: text }) =>
        csrfFetch(path, {
          method,
          ...(text === ""
            ? {}
            : { headers: { "Content-Type": "application/json" }, body: text }),
        }),
      parse: parseProviderStatus,
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
        CREDENTIAL,
        "PUT",
        { draft_key: draft, expected_version: version },
        KEY_SAVED,
      ),
    validate: () => send(VALIDATE, "POST", undefined, KEY_VALIDATED),
    disconnect: (version) =>
      send(
        CREDENTIAL,
        "DELETE",
        { expected_version: version },
        KEY_DISCONNECTED,
      ),
  };
}
