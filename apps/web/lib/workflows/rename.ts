/**
 * What the editor's name field sends and says (Decision 0037 N2): the name trimmed, under
 * creation's rule, and never a blank one. Pure and JSX-free, so `node --test` covers it.
 */

/** Creation's longest name (`WorkflowCreate.name`), which a rename keeps. */
export const NAME_MAX = 100;

export const NAME_SAVED = "Name saved. No version changed.";
export const BLANK_NAME = "A workflow needs a name.";
export const NAME_LOST =
  "The reply was lost, so it may have been saved. Pressing again sends what's on screen.";
export const NAME_NOT_SAVED = "The name could not be saved.";

// The rename's refusals, in this screen's words. A taken name is worded as creation words it
// (components/workflows/workflows-panel.tsx).
export const RENAME_REFUSALS: Readonly<Record<string, string>> = {
  workflow_name_taken: "That name is already used.",
  owner_required: "Only the workspace owner can rename a workflow.",
};

/** The trimmed name to send, or null when only spaces were typed, so nothing is sent. */
export function nameToSend(typed: string): string | null {
  const trimmed = typed.trim();
  return trimmed === "" ? null : trimmed;
}

/** What the editor says when a rename isn't accepted: refused, or its reply lost (`unknown`). */
export function renameRefusal(outcome: string, code?: string): string {
  if (outcome === "unknown") return NAME_LOST;
  return RENAME_REFUSALS[code ?? ""] ?? NAME_NOT_SAVED;
}
