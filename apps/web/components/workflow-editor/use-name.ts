/**
 * The workflow's name (Decision 0037). A save replaces it whole and carries no key, so each press
 * sends what's on screen, trimmed, one at a time, and changes no version. A blank name is never
 * sent (N2).
 */
import {
  renameWorkflow,
  type WorkflowRename,
  type WorkflowView,
} from "@autobots/api-client";
import { useState } from "react";

import { writes } from "@/lib/api/browser";
import { useSubmit } from "@/lib/use-submit";
import {
  BLANK_NAME,
  NAME_SAVED,
  nameToSend,
  renameRefusal,
} from "@/lib/workflows/rename";

export interface NameDraft {
  text: string;
  edit: (text: string) => void;
  save: () => Promise<void>;
  pending: boolean;
}

export function useName(
  workflow: WorkflowView,
  onSaved: (view: WorkflowView) => void,
  say: (message: string | null) => void,
): NameDraft {
  const saves = useSubmit<WorkflowRename>();
  // Null while the field shows the saved name.
  const [edited, setEdited] = useState<string | null>(null);
  const text = edited ?? workflow.name;

  async function save(): Promise<void> {
    say(null);
    const sent = nameToSend(text);
    if (sent === null) {
      say(BLANK_NAME);
      return;
    }
    const result = await saves.submit({
      body: () => ({ name: sent }),
      send: ({ body }) => renameWorkflow(writes, workflow.id, body),
      keyed: false,
    });
    if (result === null) return;
    if (result.outcome === "accepted" && result.value !== null) {
      onSaved(result.value);
      setEdited(null);
      say(NAME_SAVED);
      return;
    }
    say(renameRefusal(result.outcome, result.refusal?.code));
  }

  return { text, edit: setEdited, save, pending: saves.pending };
}
