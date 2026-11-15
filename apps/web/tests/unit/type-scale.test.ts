/**
 * R-68: the type, radius and spacing steps that `cn` knows are the ones app/globals.css defines, and
 * `cn` merges a step with the classes it replaces while keeping the color beside it.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import {
  RADIUS_STEPS,
  SPACING_STEPS,
  TYPE_STEPS,
} from "../../lib/type-scale.ts";
import { cn } from "../../lib/utils.ts";

const css = readFileSync(
  new URL("../../app/globals.css", import.meta.url),
  "utf8",
);

const theme = /@theme inline \{([\s\S]*?)\n\}/.exec(css)?.[1] ?? "";

function themeNames(prefix: string): string[] {
  return [...theme.matchAll(new RegExp(`--${prefix}-([a-z0-9-]+):`, "g"))].map(
    (match) => match[1] ?? "",
  );
}

test("cn knows exactly the steps the stylesheet defines", () => {
  assert.deepEqual(themeNames("text"), [...TYPE_STEPS]);
  assert.deepEqual(
    themeNames("radius").filter(
      (name) => !/^(sm|md|lg|xl|2xl|3xl|4xl)$/.test(name),
    ),
    [...RADIUS_STEPS],
  );
  assert.deepEqual(themeNames("spacing"), [...SPACING_STEPS]);
});

test("no type step sets a line height, so line height still comes from the element", () => {
  for (const step of TYPE_STEPS) {
    assert.equal(theme.includes(`--text-${step}--line-height`), false, step);
  }
});

test("no type step reuses a color's name", () => {
  const colors = new Set(themeNames("color"));
  for (const step of TYPE_STEPS) assert.equal(colors.has(step), false, step);
});

test("a type step replaces another size and keeps the text color", () => {
  assert.equal(
    cn("text-muted-foreground text-sm", "text-meta"),
    "text-muted-foreground text-meta",
  );
  assert.equal(cn("text-ui", "text-[13px]"), "text-[13px]");
  assert.equal(cn("text-foreground text-ui"), "text-foreground text-ui");
});

test("a type step drops an earlier leading, as an arbitrary size does", () => {
  assert.equal(cn("leading-tight", "text-display"), "text-display");
  assert.equal(
    cn("text-display", "leading-tight"),
    "text-display leading-tight",
  );
});

test("the radius and spacing steps merge in their own groups", () => {
  assert.equal(cn("rounded-lg", "rounded-inset"), "rounded-inset");
  assert.equal(cn("size-1.5", "size-dot"), "size-dot");
  assert.equal(cn("bg-border size-dot"), "bg-border size-dot");
});
