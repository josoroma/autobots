import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import { resolveEnvironmentKey } from "../../lib/credential-precedence.ts";

const cases = JSON.parse(
  readFileSync(
    new URL(
      "../../../../contracts/fixtures/credential-precedence.json",
      import.meta.url,
    ),
    "utf8",
  ),
) as {
  name: string;
  mode: string;
  process: Record<string, string>;
  files: Record<string, string>;
  expected: { source: string; value: string } | null;
}[];

for (const item of cases) {
  test(`shared precedence case: ${item.name}`, () => {
    const root = mkdtempSync(join(tmpdir(), "autobots-precedence-"));
    try {
      for (const [name, content] of Object.entries(item.files)) {
        writeFileSync(join(root, name), content);
      }
      assert.deepEqual(
        resolveEnvironmentKey(item.process, root, item.mode),
        item.expected,
      );
    } finally {
      rmSync(root, { recursive: true });
    }
  });
}

test("a relative root is refused", () => {
  assert.throws(() =>
    resolveEnvironmentKey({}, "relative/config", "development"),
  );
});
