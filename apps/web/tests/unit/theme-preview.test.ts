/** WSYS-19: each Appearance swatch repeats the exact luma.css declaration it names, in its theme. */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { PREVIEW_TOKENS, PREVIEWS } from "../../lib/theme-preview.ts";

const luma = readFileSync(
  new URL("../../../../docs/design/luma.css", import.meta.url),
  "utf8",
);

function block(selector: string): Map<string, string> {
  const start = luma.indexOf(`${selector} {`);
  assert.notEqual(start, -1, selector);
  const body = luma.slice(start, luma.indexOf("}", start));
  return new Map(
    [...body.matchAll(/(--[a-z0-9-]+):\s*([^;]+);/g)].map((match) => [
      match[1] ?? "",
      (match[2] ?? "").trim(),
    ]),
  );
}

const TOKENS = { light: block(":root"), dark: block(".dark") };

test("every swatch equals the luma.css value it names", () => {
  for (const theme of ["light", "dark"] as const) {
    for (const [part, utility] of Object.entries(PREVIEWS[theme])) {
      const name =
        PREVIEW_TOKENS[theme][part as keyof (typeof PREVIEWS)["dark"]];
      const value = /^bg-\[(oklch\([^\]]+\))\]$/
        .exec(utility)?.[1]
        ?.replaceAll("_", " ");
      assert.equal(value, TOKENS[theme].get(name), `${theme} ${part}`);
    }
  }
});
