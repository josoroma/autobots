/**
 * What the run would use for the current choices, from the server (PRD-Studio HM-03). Reading it
 * starts nothing. Its budget range sets the budget chip (Decision 0022 D11).
 */
import { parseRunPreview, type RunPreview } from "@autobots/api-client";
import { useState } from "react";

import { NO_EXPERT } from "@/components/composer/use-run-options";
import { worstFailure } from "@/lib/load";
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

function previewPath(profile: string, expertId: string): string {
  const query = new URLSearchParams();
  if (profile !== "") query.set("run_profile", profile);
  if (expertId !== NO_EXPERT) query.set("expert_id", expertId);
  const suffix = query.toString();
  return `/api/v1/run-preview${suffix === "" ? "" : `?${suffix}`}`;
}

export function useRunPreview(
  profile: string,
  expertId: string,
): RunPreviewRead {
  const read = useResource(previewPath(profile, expertId), parseRunPreview);
  const ready = read.state.kind === "ready" ? read.state.value : null;
  const [kept, setKept] = useState<RunPreview | null>(null);
  if (ready !== null && ready !== kept) setKept(ready);
  return {
    preview: ready ?? kept,
    failed: worstFailure([read.state]) !== null,
  };
}
