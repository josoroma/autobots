/**
 * The workflow's optional description (PRD-Studio WF-06). A save replaces it whole and carries no
 * key, so each press sends what's on screen, one at a time (Decision 0027 D2), and changes no
 * version.
 */
import {
  setWorkflowDescription,
  type WorkflowDescription,
  type WorkflowView,
} from "@autobots/api-client";
import { useState } from "react";

import { writes } from "@/lib/api/browser";
import { useSubmit } from "@/lib/use-submit";

// The description write's refusals, in this screen's words (R-19 step 4).
const DESCRIPTION_REFUSALS: Readonly<Record<string, string>> = {
  owner_required: "Only the workspace owner can describe a workflow.",
};

export interface DescriptionDraft {
  text: string;
  edit: (text: string) => void;
  save: () => Promise<void>;
  pending: boolean;
}

export function useDescription(
  workflow: WorkflowView,
  onSaved: (view: WorkflowView) => void,
  say: (message: string | null) => void,
): DescriptionDraft {
  const saves = useSubmit<WorkflowDescription>();
  // Null while the field shows the saved description.
  const [edited, setEdited] = useState<string | null>(null);
  const text = edited ?? workflow.description ?? "";

  async function save(): Promise<void> {
    say(null);
    const sent = text.trim();
    const result = await saves.submit({
      body: () => ({ description: sent === "" ? null : sent }),
      send: ({ body }) => setWorkflowDescription(writes, workflow.id, body),
      keyed: false,
    });
    if (result === null) return;
    if (result.outcome === "accepted" && result.value !== null) {
      const saved = result.value;
      onSaved(saved);
      setEdited(null);
      say(
        saved.description === null
          ? "The description is removed. No version changed."
          : "Description saved. No version changed.",
      );
      return;
    }
    say(
      result.outcome === "unknown"
        ? "The reply was lost, so it may have been saved. Pressing again sends what's on screen."
        : (DESCRIPTION_REFUSALS[result.refusal?.code ?? ""] ??
            "The description could not be saved."),
    );
  }

  return { text, edit: setEdited, save, pending: saves.pending };
}
