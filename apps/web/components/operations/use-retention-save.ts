/**
 * Saves the retention windows (WSYS-01, R-19). One save at a time; it sends no key and replaces the
 * windows whole, so it's never held. An accepted save reads the status again through `onSaved`.
 */
import { setRetention, type RetentionSettings } from "@autobots/api-client";
import { useState } from "react";

import { writes } from "@/lib/api/browser";
import { retentionOutcome } from "@/lib/retention";
import { useSubmit } from "@/lib/use-submit";

export interface RetentionSave {
  pending: boolean;
  /** What the newest save said, or null. */
  message: string | null;
  /** Sends the body `request` returns, or nothing when it returns null. */
  save: (request: () => RetentionSettings | null) => Promise<void>;
}

export function useRetentionSave(onSaved: () => void): RetentionSave {
  const saves = useSubmit<RetentionSettings>();
  const [message, setMessage] = useState<string | null>(null);

  async function save(request: () => RetentionSettings | null): Promise<void> {
    setMessage(null);
    const result = await saves.submit({
      body: request,
      send: ({ body }) => setRetention(writes, body),
      keyed: false,
    });
    if (result === null) return;
    const accepted = result.outcome === "accepted";
    // A refused save keeps what was typed, so it can be corrected.
    setMessage(retentionOutcome(accepted, result.refusal));
    if (accepted) onSaved();
  }

  return { pending: saves.pending, message, save };
}
