/**
 * The stored result the run page shows (R-49, WRUN-01): a published artifact's text, read only when
 * it is text, and nothing when it can't be read, so the live text or nothing stays shown.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import { readStoredText } from "../../lib/runs/published-result.ts";

const ARTIFACT = "33333333-3333-4333-8333-333333333333";

function serve(
  body: string,
  init: ResponseInit,
  asked: { url: string; init: RequestInit | undefined }[] = [],
): typeof globalThis.fetch {
  return async (input, options) => {
    asked.push({ url: String(input), init: options });
    return new Response(body, init);
  };
}

test("a text or JSON artifact is read from its download route, uncached", async () => {
  const asked: { url: string; init: RequestInit | undefined }[] = [];
  const text = await readStoredText(`${ARTIFACT}/x`, {
    fetch: serve(
      "# Report",
      { headers: { "content-type": "text/markdown" } },
      asked,
    ),
  });
  assert.equal(text, "# Report");
  assert.equal(
    asked[0]?.url,
    `/api/v1/artifacts/${encodeURIComponent(`${ARTIFACT}/x`)}/download`,
  );
  assert.equal(asked[0]?.init?.cache, "no-store");
  assert.equal(
    await readStoredText(ARTIFACT, {
      fetch: serve('{"a":1}', {
        headers: { "content-type": "application/json" },
      }),
    }),
    '{"a":1}',
  );
});

test("an artifact that isn't text, a refusal or no reply shows nothing", async () => {
  assert.equal(
    await readStoredText(ARTIFACT, {
      fetch: serve("PNG", { headers: { "content-type": "image/png" } }),
    }),
    null,
  );
  // A reply with no body says no type.
  assert.equal(
    await readStoredText(ARTIFACT, {
      fetch: async () => new Response(null, { status: 200 }),
    }),
    null,
  );
  assert.equal(
    await readStoredText(ARTIFACT, {
      fetch: serve("{}", {
        status: 404,
        headers: { "content-type": "text/plain" },
      }),
    }),
    null,
  );
  const offline: typeof globalThis.fetch = async () => {
    throw new TypeError("offline");
  };
  assert.equal(await readStoredText(ARTIFACT, { fetch: offline }), null);
});

test("a read that a newer one replaced is aborted and shows nothing", async () => {
  const controller = new AbortController();
  const waiting: typeof globalThis.fetch = (_input, init) =>
    new Promise((_resolve, reject) => {
      init?.signal?.addEventListener("abort", () =>
        reject(new DOMException("aborted", "AbortError")),
      );
    });
  const read = readStoredText(ARTIFACT, {
    fetch: waiting,
    signal: controller.signal,
  });
  controller.abort();
  assert.equal(await read, null);
});
