/**
 * The saved policy and the form's draft of it (WSYS-06). Both start from the read, and a write's
 * reply or Discard adopts a policy as saved and resets the draft to it. Derived during render, so
 * no effect copies the read into state.
 */
import type { ModelPolicyState } from "@autobots/api-client";
import { useCallback, useState } from "react";

import {
  draftOf,
  sameForm,
  withOverride,
  type PolicyDraft,
} from "@/lib/model-policy";
import { profileChoice } from "@/lib/model-profile";

interface Own {
  saved: ModelPolicyState;
  draft: PolicyDraft;
}

export interface PolicyDraftState {
  /** The policy as saved: the newest write's reply, or else the read. Null before the read. */
  saved: ModelPolicyState | null;
  draft: PolicyDraft | null;
  /** The draft differs from what's saved. */
  dirty: boolean;
  adopt: (next: ModelPolicyState) => void;
  setDefault: (profile: string) => void;
  setOverride: (role: string, profile: string) => void;
}

export function usePolicyDraft(
  read: ModelPolicyState | null,
): PolicyDraftState {
  const [own, setOwn] = useState<Own | null>(null);
  const saved = own?.saved ?? read;
  const draft = own?.draft ?? (read === null ? null : draftOf(read));
  const adopt = useCallback(
    (next: ModelPolicyState) => setOwn({ saved: next, draft: draftOf(next) }),
    [],
  );

  function edit(change: (current: PolicyDraft) => PolicyDraft): void {
    if (saved === null || draft === null) return;
    setOwn({ saved, draft: change(draft) });
  }

  return {
    saved,
    draft,
    dirty: saved !== null && draft !== null && !sameForm(saved, draft),
    adopt,
    // A value that isn't a profile is ignored, so it never becomes a default (MP-A08).
    setDefault: (value) => {
      const profile = profileChoice(value);
      if (profile !== null)
        edit((current) => ({ ...current, defaultProfile: profile }));
    },
    setOverride: (role, value) => {
      const profile = profileChoice(value);
      if (profile !== null)
        edit((current) => ({
          ...current,
          overrides: withOverride(current.overrides, role, profile),
        }));
    },
  };
}
