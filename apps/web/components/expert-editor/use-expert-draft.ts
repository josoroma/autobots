/**
 * The Expert editor's draft and its save (WBLD-10). A save posts a revision bound to the version the
 * form was read from, keeps what the form doesn't edit, and says its outcome from one table. One key
 * per intent until its outcome is known; while a save is held, the fields it sent stay as sent
 * (Decision 0027 D2).
 */
import {
  parseExpertView,
  type ExpertView,
  type ModelList,
} from "@autobots/api-client";
import { useState, type FormEvent } from "react";

import { csrfFetch } from "@/lib/csrf-fetch";
import {
  draftOf,
  revisionBody,
  revisionText,
  splitBindings,
  type Draft,
} from "@/lib/experts/draft";
import { useSubmit } from "@/lib/use-submit";

export interface ExpertDraft {
  draft: Draft;
  setDraft: (draft: Draft) => void;
  save: (event: FormEvent) => Promise<void>;
  pending: boolean;
  /** A save is held, so its fields stay as sent. */
  held: boolean;
  /** Roles whose saved model isn't offered for new runs, which this save removes. */
  dropped: readonly string[];
}

export function useExpertDraft(
  expert: ExpertView,
  models: ModelList | null,
  onSaved: (view: ExpertView) => void,
  say: (message: string | null) => void,
): ExpertDraft {
  const revisions = useSubmit();
  const [draft, setDraft] = useState<Draft>(() => draftOf(expert));
  const { kept, dropped } = splitBindings(expert, models);

  async function save(event: FormEvent): Promise<void> {
    event.preventDefault();
    say(null);
    const result = await revisions.submit({
      body: () => revisionBody(expert, draft, kept),
      send: ({ key, body }) =>
        csrfFetch(`/api/v1/experts/${encodeURIComponent(expert.id)}/versions`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": key,
          },
          body,
        }),
      parse: parseExpertView,
    });
    if (result === null) return;
    if (result.outcome === "accepted" && result.value !== null) {
      onSaved(result.value);
      setDraft(draftOf(result.value));
    }
    say(revisionText(result));
  }

  return {
    draft,
    setDraft,
    save,
    pending: revisions.pending,
    held: revisions.holding(),
    dropped,
  };
}
