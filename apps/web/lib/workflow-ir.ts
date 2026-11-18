/**
 * The workflow editor's reading of its graph text, and its one copy of PRD-Studio WF-06's label
 * rule. The domain's `ir_normalized` owns that rule; both run the cases in
 * contracts/fixtures/workflow-label-rule.json, so the two can't disagree on any case (Decision 0029
 * F1). Pure and JSX-free, so `node --test` loads it.
 */
import type { WorkflowGraph, WorkflowNode } from "@autobots/api-client";

/** The IR version a graph whose nodes carry labels is stored at (PRD-Studio WF-06). */
export const LABELLED_IR_VERSION = 2;

/** A step as the label fields read it. Its other fields pass through unchanged. */
export type LabelNode = Pick<WorkflowNode, "id" | "block" | "label">;

/** A graph as the label rule reads it: a view's, a fixture's or the editor's. */
export interface IrGraph {
  nodes?: readonly LabelNode[];
  ir_version?: number | null;
}

/** The graph the editor's text holds, once its steps are known to carry an id and a block. */
export interface EditorGraph {
  nodes: LabelNode[];
  ir_version?: number | null;
}

/** What a new workflow's editor opens with: one input linked to one output, at IR version 1. */
export const STARTER_GRAPH = {
  nodes: [
    { id: "in", block: "input", version: 1, config: { type: "string" } },
    { id: "out", block: "output", version: 1 },
  ],
  links: [
    { source: "in", source_port: "value", target: "out", target_port: "value" },
  ],
} satisfies WorkflowGraph;

function hasLabels(nodes: readonly LabelNode[]): boolean {
  return nodes.some((node) => "label" in node);
}

function withoutNullLabel(node: LabelNode): LabelNode {
  const plain = { ...node };
  if (plain.label === null) delete plain.label;
  return plain;
}

/**
 * As the domain stores and hashes a graph (`ir_normalized`): a null label or IR version is left
 * out, so a version 1 graph is unchanged, and a graph with no IR version whose nodes carry labels
 * is stored at version 2. A graph that declares a version keeps it, with or without labels, so
 * clearing the last label leaves version 2 in place. Returns a new graph.
 */
export function irNormalized(graph: IrGraph): EditorGraph {
  const plain: EditorGraph = {
    ...graph,
    nodes: (graph.nodes ?? []).map(withoutNullLabel),
  };
  if (plain.ir_version === null || plain.ir_version === undefined) {
    delete plain.ir_version;
    if (hasLabels(plain.nodes)) {
      plain.ir_version = LABELLED_IR_VERSION;
    }
  }
  return plain;
}

/** A graph as the editor shows it: normalized and indented, so its stored form and hash stay. */
export function graphText(graph: IrGraph): string {
  return JSON.stringify(irNormalized(graph), null, 2);
}

/**
 * The JSON a text holds, or null when it isn't JSON. JSON `null` reads as null too, as no request
 * the editor sends takes it.
 */
export function parseJsonText(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isLabelNode(value: unknown): value is LabelNode {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.block === "string" &&
    (value.label === undefined ||
      value.label === null ||
      typeof value.label === "string")
  );
}

/** The graph a JSON value holds, or null when a step lacks an id or a block. */
export function editorGraph(value: unknown): EditorGraph | null {
  if (!isRecord(value) || !Array.isArray(value.nodes)) return null;
  const version = value.ir_version;
  if (version !== undefined && version !== null && typeof version !== "number")
    return null;
  const nodes: unknown[] = value.nodes;
  if (!nodes.every(isLabelNode)) return null;
  return { ...value, nodes };
}

/** The graph a text holds, for its step labels, or null. */
export function parseGraphText(text: string): EditorGraph | null {
  return editorGraph(parseJsonText(text));
}

/**
 * The graph with one step's label set, or removed when blank, then normalized under the domain's
 * rule above (PRD-Studio WF-06). An edit that leaves a step labelled on a graph declared at IR
 * version 1 also raises it to 2, as the label fields' hint says a labelled graph is published at 2:
 * the domain keeps a declared version and refuses labels at 1. Normalizing alone keeps 1, as the
 * shared fixtures require.
 */
export function withLabel(
  graph: EditorGraph,
  nodeId: string,
  label: string,
): EditorGraph {
  const nodes = graph.nodes.map((node) => {
    if (node.id !== nodeId) return node;
    const next = { ...node };
    if (label.trim() === "") delete next.label;
    else next.label = label;
    return next;
  });
  const labelled = irNormalized({ ...graph, nodes });
  if (labelled.ir_version === 1 && hasLabels(labelled.nodes)) {
    labelled.ir_version = LABELLED_IR_VERSION;
  }
  return labelled;
}
