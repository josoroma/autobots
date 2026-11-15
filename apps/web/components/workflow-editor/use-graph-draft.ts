/**
 * The editor's graph text beside its baseline, the saved WF-02 draft or else the newest version,
 * and every action on them (PRD-Studio WF-02, WBLD-05). The text is parsed once per change and
 * checked as JSON in one place before anything is sent. It is dirty while it differs from the
 * baseline, so the saved draft can't be published from under unsaved edits.
 */
import {
  discardWorkflowDraft,
  parseWorkflowValidation,
  parseWorkflowView,
  publishWorkflowDraft,
  type WorkflowDraftPublish,
  type WorkflowDraftSave,
  type WorkflowPublish,
  type WorkflowValidation,
  type WorkflowView,
} from "@autobots/api-client";
import { useMemo, useState } from "react";

import { writeAsTyped, writes as writeClient } from "@/lib/api/browser";
import { refusalText, withHeld } from "@/lib/submit";
import { useSubmit, type Submitted } from "@/lib/use-submit";
import {
  editorGraph,
  graphText,
  parseJsonText,
  STARTER_GRAPH,
  withLabel,
  type EditorGraph,
} from "@/lib/workflow-ir";
import {
  draftRoute,
  publishRoute,
  VALIDATE_ROUTE,
} from "@/lib/workflows/unchecked-writes";

const NOT_JSON = "That isn't valid JSON.";
const NOTHING_CHANGED = "That could not be done. Nothing changed.";

// The draft writes' refusals, in this screen's words (R-19 step 4).
const DRAFT_REFUSALS: Readonly<Record<string, string>> = {
  owner_required: "Only the workspace owner can change the draft.",
  workflow_version_conflict:
    "A newer version was published, so the draft wasn't. Reload and try again.",
};

/**
 * A body whose graph is the person's, as they typed it. Only the service validates a graph
 * (PRD-Studio WF-02), so the editor sends it unchecked, and the rest of the body keeps its
 * generated type (R-48).
 */
type WithTypedGraph<B> = Omit<B, "graph"> & { graph: unknown };

export interface GraphDraft {
  /** What the Graph field shows. */
  text: string;
  /** The saved draft, or else the newest version, or the starter graph, as the editor shows it. */
  baseline: string;
  isDirty: boolean;
  /** The text's graph for its step labels, or null when it isn't one. */
  graph: EditorGraph | null;
  check: WorkflowValidation | null;
  edit: (text: string) => void;
  label: (nodeId: string, label: string) => void;
  validate: () => Promise<void>;
  /** Publishes the text as the next version, leaving any saved draft in place. */
  publish: () => Promise<void>;
  save: () => Promise<void>;
  /** Publishes the saved draft, which the text must match. */
  publishSaved: () => Promise<void>;
  discard: () => Promise<void>;
  publishing: boolean;
  /** A publish of the text is held, so the text stays as it was sent (Decision 0027 D2). */
  publishHeld: boolean;
  /** Publishing or discarding the saved draft is pending. */
  draftBusy: boolean;
}

function baselineOf(workflow: WorkflowView): string {
  const graph =
    workflow.draft?.graph ?? workflow.versions.at(-1)?.graph ?? STARTER_GRAPH;
  return graphText(graph);
}

function draftWords(result: Submitted<WorkflowView>, keyed: boolean): string {
  if (result.outcome === "unknown") {
    return keyed
      ? "The reply was lost, so this may have applied. Pressing again won't repeat it."
      : "The reply was lost, so this may have applied. Pressing again sends what's on screen, which replaces the draft as a whole.";
  }
  return withHeld(
    refusalText(DRAFT_REFUSALS, result.refusal, NOTHING_CHANGED),
    result.held,
  );
}

function publishWords(result: Submitted<WorkflowView>): string {
  if (result.outcome === "unknown") {
    return "The reply was lost, so it may have been published. Pressing again won't publish it twice.";
  }
  return withHeld(
    result.refusal?.code === "owner_required"
      ? "Only the workspace owner can publish."
      : (result.refusal?.message ?? "That could not be published."),
    result.held,
  );
}

/** validateWorkflow's check of a graph, or null when it refused the shape or didn't answer. */
async function checkGraph(json: unknown): Promise<WorkflowValidation | null> {
  try {
    return await writeAsTyped(VALIDATE_ROUTE, json, parseWorkflowValidation);
  } catch {
    return null;
  }
}

export function useGraphDraft(
  workflow: WorkflowView,
  onSaved: (view: WorkflowView) => void,
  say: (message: string | null) => void,
): GraphDraft {
  // One write at a time, and one key per intent until its outcome is known (Decision 0027 D2).
  // PRD-Studio WF-02: one saved draft, published under the expected version or discarded. Only
  // publishing carries a key; a save or a discard replaces the draft whole, so each press sends
  // the latest and nothing is held.
  const publishing = useSubmit<WithTypedGraph<WorkflowPublish>>();
  const saves = useSubmit<WithTypedGraph<WorkflowDraftSave>>();
  const discards = useSubmit<undefined>();
  const draftPublishes = useSubmit<WorkflowDraftPublish>();
  const baseline = useMemo(() => baselineOf(workflow), [workflow]);
  // Null while the text follows the baseline.
  const [edited, setEdited] = useState<string | null>(null);
  const [check, setCheck] = useState<WorkflowValidation | null>(null);
  const text = edited ?? baseline;
  const isDirty = text !== baseline;
  const json = useMemo(() => parseJsonText(text), [text]);
  const graph = useMemo(() => editorGraph(json), [json]);

  function edit(next: string): void {
    setEdited(next);
    setCheck(null);
  }

  // After an accepted write, the text follows the new baseline, unless it changed since sent.
  function follow(sent: string): void {
    setEdited((current) =>
      current === null || current === sent ? null : current,
    );
  }

  /** What a draft write's reply leaves: the saved view, or null once it has said why not. */
  function settled(
    result: Submitted<WorkflowView> | null,
    keyed: boolean,
  ): WorkflowView | null {
    // A press while the same write is pending sends nothing, so it says nothing.
    if (result === null) return null;
    if (result.outcome === "accepted" && result.value !== null) {
      onSaved(result.value);
      return result.value;
    }
    say(draftWords(result, keyed));
    return null;
  }

  async function validate(): Promise<void> {
    say(null);
    if (json === null) {
      setCheck(null);
      say(NOT_JSON);
      return;
    }
    const checked = await checkGraph(json);
    setCheck(checked);
    if (checked === null) say("That has the wrong shape for a workflow.");
  }

  async function publish(): Promise<void> {
    say(null);
    if (json === null) {
      say(NOT_JSON);
      return;
    }
    const sent = text;
    const result = await publishing.submit({
      body: () => ({ expected_version: workflow.latest_version, graph: json }),
      send: ({ key, body }) =>
        writeAsTyped(publishRoute(workflow.id), body, parseWorkflowView, key),
    });
    if (result === null) return;
    if (result.outcome !== "accepted" || result.value === null) {
      say(publishWords(result));
      return;
    }
    const saved = result.value;
    onSaved(saved);
    // A saved draft stays the baseline, so the published text stays shown, and dirty beside it.
    if (saved.draft === null) follow(sent);
    say(
      `Published as version ${saved.latest_version}. Earlier versions don't change.`,
    );
  }

  async function save(): Promise<void> {
    say(null);
    if (json === null) {
      say(NOT_JSON);
      return;
    }
    const sent = text;
    const result = await saves.submit({
      body: () => ({ graph: json }),
      send: ({ body }) =>
        writeAsTyped(draftRoute(workflow.id), body, parseWorkflowView),
      keyed: false,
    });
    if (settled(result, false) === null) return;
    follow(sent);
    say("Draft saved. Runs keep using the published versions.");
  }

  async function publishSaved(): Promise<void> {
    if (isDirty) return;
    say(null);
    const sent = text;
    const result = await draftPublishes.submit({
      body: () => ({ expected_version: workflow.latest_version }),
      send: ({ key, body }) =>
        publishWorkflowDraft(writeClient, workflow.id, body, {
          "Idempotency-Key": key,
        }),
    });
    const view = settled(result, true);
    if (view === null) return;
    follow(sent);
    say(
      `Published the draft as version ${view.latest_version}. Earlier versions don't change.`,
    );
  }

  async function discard(): Promise<void> {
    say(null);
    const result = await discards.submit({
      body: () => undefined,
      send: () => discardWorkflowDraft(writeClient, workflow.id),
      keyed: false,
    });
    if (settled(result, false) === null) return;
    setEdited(null);
    setCheck(null);
    say("Draft discarded. The published versions are unchanged.");
  }

  return {
    text,
    baseline,
    isDirty,
    graph,
    check,
    edit,
    label: (nodeId, label) => {
      if (graph !== null) {
        edit(JSON.stringify(withLabel(graph, nodeId, label), null, 2));
      }
    },
    validate,
    publish,
    save,
    publishSaved,
    discard,
    publishing: publishing.pending,
    publishHeld: publishing.holding(),
    draftBusy: draftPublishes.pending || discards.pending,
  };
}
