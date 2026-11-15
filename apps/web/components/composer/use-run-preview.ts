/**
 * What the run would use for the current choices, from the server (PRD-Studio HM-03). Reading it
 * starts nothing. Its budget range sets the budget chip (Decision 0022 D11).
 */
import {
  previewRun,
  type PreviewRunQuery,
  type RunPreview,
} from "@autobots/api-client";
import { useState } from "react";

import { NO_EXPERT } from "@/components/composer/use-run-options";
import { readOf, worstFailure } from "@/lib/load";
import { profileField } from "@/lib/model-profile";
import { useResource } from "@/lib/use-resource";

export interface RunPreviewRead {
  /**
   * The newest preview read, kept while a later choice's preview is pending or has failed, so the
   * budget chip keeps the last range the server sent.
   */
  preview: RunPreview | null;
  /** The newest read failed, so the chips can't say what the run would use. */
  failed: boolean;
}

/**
 * What a preview asks about, with defaults left out, so the first read is plain /api/v1/run-preview.
 * Null for a chosen model that isn't a profile, which the service refuses to preview
 * (PRD-Model-Providers MP-A08).
 */
function previewQuery(
  profile: string,
  expertId: string,
): PreviewRunQuery | null {
  const field = profileField(profile);
  return field === null
    ? null
    : {
        run_profile: field.run_profile,
        expert_id: expertId === NO_EXPERT ? undefined : expertId,
      };
}

export function useRunPreview(
  profile: string,
  expertId: string,
): RunPreviewRead {
  const query = previewQuery(profile, expertId);
  const read = useResource(query === null ? null : readOf(previewRun, query));
  const ready = read.state.kind === "ready" ? read.state.value : null;
  const [kept, setKept] = useState<RunPreview | null>(null);
  if (ready !== null && ready !== kept) setKept(ready);
  return {
    preview: ready ?? kept,
    failed: query === null || worstFailure([read.state]) !== null,
  };
}
