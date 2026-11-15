/**
 * Saves and resets the role policy (PRD-Studio MD-02 and MD-03, R-19). One write at a time.
 * Neither sends a key, and each replaces the policy whole, so none is held. An accepted reply is
 * adopted as saved; any other says why in this screen's words.
 */
import {
  putModelPolicy,
  resetModelPolicyOverrides,
  type ModelPolicyState,
} from "@autobots/api-client";
import { useState } from "react";

import { writes as writeClient } from "@/lib/api/browser";
import {
  POLICY_LOST,
  POLICY_RESET,
  POLICY_SAVED,
  policyBody,
  RESET_REFUSALS,
  resetBody,
  SAVE_REFUSALS,
  type PolicyDraft,
} from "@/lib/model-policy";
import { refusalText } from "@/lib/submit";
import { useSubmit } from "@/lib/use-submit";

interface Write {
  send: () => Promise<ModelPolicyState>;
  done: string;
  refusals: Readonly<Record<string, string>>;
}

export interface PolicyWrites {
  pending: boolean;
  /** What the newest write, or Discard, said. */
  message: string | null;
  say: (message: string) => void;
  save: (saved: ModelPolicyState, draft: PolicyDraft) => Promise<void>;
  reset: (saved: ModelPolicyState) => Promise<void>;
}

export function usePolicyWrites(
  adopt: (next: ModelPolicyState) => void,
): PolicyWrites {
  // Each press builds its own request and nothing is held (keyed: false), so the hook carries no
  // body.
  const writes = useSubmit<undefined>();
  const [message, setMessage] = useState<string | null>(null);

  async function write({ send, done, refusals }: Write) {
    setMessage(null);
    const result = await writes.submit({
      body: () => undefined,
      send,
      keyed: false,
    });
    if (result === null) return;
    if (result.outcome === "accepted" && result.value !== null) {
      adopt(result.value);
      setMessage(done);
      return;
    }
    setMessage(refusalText(refusals, result.refusal, POLICY_LOST));
  }

  return {
    pending: writes.pending,
    message,
    say: setMessage,
    save: (saved, draft) =>
      write({
        send: () => putModelPolicy(writeClient, policyBody(saved, draft)),
        done: POLICY_SAVED,
        refusals: SAVE_REFUSALS,
      }),
    reset: (saved) =>
      write({
        send: () => resetModelPolicyOverrides(writeClient, resetBody(saved)),
        done: POLICY_RESET,
        refusals: RESET_REFUSALS,
      }),
  };
}
