/**
 * Pins how an approval's exact request is read for its Fields view (WTAP-09, R-45): the stored
 * order kept, so a request whose keys JSON would reorder has no Fields view (PRD-Studio AP-03), and
 * a text field's Markdown read into text parts only, so nothing is injected as HTML.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  inlineParts,
  markdownBlocks,
  parsedFields,
  readsAsMarkdown,
} from "../../lib/approval-fields.ts";

function fields(text: string, truncated = false) {
  return parsedFields({ arguments: text, arguments_truncated: truncated });
}

test("Fields keep the stored order, and every value as stored", () => {
  assert.deepEqual(
    fields('{"to":"team@example.invalid","body":"hello","cc":["a"],"n":2}'),
    [
      ["to", "team@example.invalid"],
      ["body", "hello"],
      ["cc", ["a"]],
      ["n", 2],
    ],
  );
  assert.deepEqual(fields('{"z":{"b":1,"a":2},"a":null}'), [
    ["z", { b: 1, a: 2 }],
    ["a", null],
  ]);
});

test("a request with an integer-like key has no Fields view, since JSON would reorder it", () => {
  assert.equal(fields('{"to":"x","10":"ten","2":"two"}'), null);
  assert.equal(fields('{"0":"zero"}'), null);
  // Only a whole key of digits reorders, so these keep their Fields.
  assert.deepEqual(fields('{"a1":1,"-1":2,"1.5":3}'), [
    ["a1", 1],
    ["-1", 2],
    ["1.5", 3],
  ]);
});

test("a request that isn't one JSON object, or isn't shown whole, has no Fields view", () => {
  assert.equal(fields('["to","body"]'), null);
  assert.equal(fields("null"), null);
  assert.equal(fields('"text"'), null);
  assert.equal(fields("42"), null);
  assert.equal(fields("{not json"), null);
  assert.equal(fields('{"to":"x"}', true), null);
});

test("an empty object has Fields, and none to list", () => {
  assert.deepEqual(fields("{}"), []);
});

test("a text field reads as Markdown when it has a line break, code, bold or a list item", () => {
  assert.equal(readsAsMarkdown("one\ntwo"), true);
  assert.equal(readsAsMarkdown("use `Q3`"), true);
  assert.equal(readsAsMarkdown("**Totals**"), true);
  assert.equal(readsAsMarkdown("- one item"), true);
  assert.equal(readsAsMarkdown("text\n* item"), true);
  assert.equal(readsAsMarkdown("plain words"), false);
  assert.equal(readsAsMarkdown("a - b * c"), false);
});

test("inline Markdown splits into text, code and bold parts", () => {
  assert.deepEqual(inlineParts("**Totals** for `Q3`:"), [
    { kind: "strong", text: "Totals" },
    { kind: "text", text: " for " },
    { kind: "code", text: "Q3" },
    { kind: "text", text: ":" },
  ]);
  assert.deepEqual(inlineParts("plain"), [{ kind: "text", text: "plain" }]);
  // Unclosed or empty markers stay as typed.
  assert.deepEqual(inlineParts("a ` b ** c"), [
    { kind: "text", text: "a ` b ** c" },
  ]);
  assert.deepEqual(inlineParts("empty `` and ****"), [
    { kind: "text", text: "empty `` and ****" },
  ]);
});

test("blank lines separate blocks, and a block of list items is a list", () => {
  assert.deepEqual(
    markdownBlocks("**Totals** for `Q3`:\n\n- one item\n* two items"),
    [
      {
        kind: "paragraph",
        lines: [
          [
            { kind: "strong", text: "Totals" },
            { kind: "text", text: " for " },
            { kind: "code", text: "Q3" },
            { kind: "text", text: ":" },
          ],
        ],
      },
      {
        kind: "list",
        items: [
          [{ kind: "text", text: "one item" }],
          [{ kind: "text", text: "two items" }],
        ],
      },
    ],
  );
});

test("a block mixing items and text stays a paragraph, one line per line", () => {
  assert.deepEqual(markdownBlocks("intro\n- item"), [
    {
      kind: "paragraph",
      lines: [
        [{ kind: "text", text: "intro" }],
        [{ kind: "text", text: "- item" }],
      ],
    },
  ]);
});
