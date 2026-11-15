/**
 * Pins the workflow editor's copy of PRD-Studio WF-06's label rule to the cases the domain's
 * ir_normalized also runs (Decision 0029 F1, WBLD-06), and the editor's reading of its text and its
 * label edits (WBLD-15).
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import type { WorkflowGraph } from "@autobots/api-client";

import {
  editorGraph,
  graphText,
  irNormalized,
  parseGraphText,
  parseJsonText,
  STARTER_GRAPH,
  withLabel,
  type EditorGraph,
  type IrGraph,
} from "../../lib/workflow-ir.ts";

const cases = JSON.parse(
  readFileSync(
    new URL(
      "../../../../contracts/fixtures/workflow-label-rule.json",
      import.meta.url,
    ),
    "utf8",
  ),
) as { name: string; graph: IrGraph; normalized: IrGraph }[];

for (const item of cases) {
  test(`shared label case: ${item.name}`, () => {
    assert.deepEqual(irNormalized(item.graph), item.normalized);
  });
  test(`a normalized graph stays as it is: ${item.name}`, () => {
    assert.deepEqual(irNormalized(item.normalized), item.normalized);
  });
}

function graph(text: string): EditorGraph {
  const read = parseGraphText(text);
  assert.notEqual(read, null);
  return read as EditorGraph;
}

const STARTER = graphText(STARTER_GRAPH);

test("normalizing leaves the graph it was given as it was", () => {
  const given = {
    nodes: [{ id: "in", block: "input", label: null }],
    ir_version: null,
  };
  irNormalized(given);
  assert.deepEqual(given, {
    nodes: [{ id: "in", block: "input", label: null }],
    ir_version: null,
  });
});

test("a label on an unlabelled graph moves it to IR version 2", () => {
  const labelled = withLabel(graph(STARTER), "out", "Answer");
  assert.equal(labelled.ir_version, 2);
  assert.equal(labelled.nodes[1]?.label, "Answer");
  assert.equal("label" in (labelled.nodes[0] ?? {}), false);
});

test("clearing the last label keeps IR version 2, as the domain's rule does", () => {
  const labelled = withLabel(graph(STARTER), "out", "Answer");
  const cleared = withLabel(labelled, "out", "");
  assert.equal(cleared.ir_version, 2);
  assert.equal("label" in (cleared.nodes[1] ?? {}), false);
});

test("a blank label is removed, and the other steps keep theirs", () => {
  const both = withLabel(withLabel(graph(STARTER), "in", "Ask"), "out", "Say");
  const one = withLabel(both, "out", "   ");
  assert.equal(one.nodes[0]?.label, "Ask");
  assert.equal("label" in (one.nodes[1] ?? {}), false);
  assert.equal(one.ir_version, 2);
});

test("a label edit keeps the fields it doesn't read", () => {
  const labelled = withLabel(graph(STARTER), "in", "Ask");
  assert.deepEqual(labelled.nodes[0], {
    id: "in",
    block: "input",
    version: 1,
    config: { type: "string" },
    label: "Ask",
  });
  assert.deepEqual(
    (labelled as EditorGraph & { links?: unknown }).links,
    STARTER_GRAPH.links,
  );
});

test("a view's graph is shown without its nulls, so its stored form and hash stay", () => {
  const view: WorkflowGraph = {
    nodes: [
      { id: "in", block: "input", version: 1, config: {}, label: null },
      { id: "out", block: "output", version: 1, config: {}, label: null },
    ],
    links: [],
    ir_version: null,
  };
  const shown = graphText(view);
  assert.equal(
    shown,
    JSON.stringify(
      {
        nodes: [
          { id: "in", block: "input", version: 1, config: {} },
          { id: "out", block: "output", version: 1, config: {} },
        ],
        links: [],
      },
      null,
      2,
    ),
  );
});

test("the starter graph is an unlabelled IR version 1 graph", () => {
  const starter = graph(STARTER);
  assert.equal("ir_version" in starter, false);
  assert.deepEqual(
    starter.nodes.map((node) => node.id),
    ["in", "out"],
  );
});

test("text that isn't JSON reads as nothing, and so does JSON null", () => {
  assert.equal(parseJsonText("{ not json"), null);
  assert.equal(parseJsonText("null"), null);
  assert.deepEqual(parseJsonText('{"in": "x"}'), { in: "x" });
  assert.deepEqual(parseJsonText("[1]"), [1]);
});

test("only a graph whose steps have an id and a block offers label fields", () => {
  for (const text of [
    "{",
    "null",
    "[]",
    '"graph"',
    '{"links": []}',
    '{"nodes": {}}',
    '{"nodes": [null]}',
    '{"nodes": [{"block": "input"}]}',
    '{"nodes": [{"id": 1, "block": "input"}]}',
    '{"nodes": [{"id": "in"}]}',
    '{"nodes": [{"id": "in", "block": "input", "label": 5}]}',
    '{"nodes": [], "ir_version": "2"}',
  ]) {
    assert.equal(parseGraphText(text), null, text);
  }
  assert.deepEqual(editorGraph({ nodes: [] }), { nodes: [] });
  assert.deepEqual(
    parseGraphText('{"nodes": [{"id": "in", "block": "input", "label": null}]}')
      ?.nodes,
    [{ id: "in", block: "input", label: null }],
  );
});
