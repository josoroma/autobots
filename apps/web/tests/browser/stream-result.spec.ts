import type { Page } from "@playwright/test";

import { expectNoA11yViolations, WCAG_22_AA } from "./support/a11y.ts";
import { signIn, users } from "./support/auth.ts";
import { objectOf } from "./support/db-helpers.ts";
import { need } from "./support/env.ts";
import { expect, test, type StartDbStream } from "./support/fixtures.ts";

// US-15.24, PRD-Studio ST-01 and Decision 0022 D4. tests/db/result_stream_live.py admits a run in the
// ops-n workspace, prints its ID, waits for the page, then writes its result with a streaming scripted
// model whose pieces are spaced out, and prints the outcome once the result is stored.
const parseOutcome = objectOf({
  run_id: "string",
  status: "string",
  durable_deltas: "number",
  content: "string",
});
type Outcome = ReturnType<typeof parseOutcome>;

/** Starts the helper. Each promise rejects, naming the helper, if it ends before printing that line. */
function launch(
  start: StartDbStream,
  delay: number,
  wait: number,
): { runId: Promise<string>; done: Promise<Outcome> } {
  const stream = start(
    "result_stream_live.py",
    [need("AUTOBOTS_TEST_OPS_WORKSPACE"), String(delay), String(wait)],
    {
      AUTOBOTS_STORAGE_BASE: need("AUTOBOTS_TEST_STORAGE_BASE"),
      AUTOBOTS_STORAGE_SERVICE: need("AUTOBOTS_TEST_SERVICE_KEY"),
    },
  );
  const runId = stream
    .next(objectOf({ run_id: "string" }))
    .then((line) => line.run_id);
  return { runId, done: stream.next(parseOutcome) };
}

const resultText = (page: Page) =>
  page.locator('[data-field="result-text"]').textContent();

test("the result appears while it's written, and then the stored artifact replaces it exactly", async ({
  page,
  dbStream,
}) => {
  test.setTimeout(90_000);
  await signIn(page, users.ops);
  const { runId, done } = launch(dbStream, 0.02, 5);
  await page.goto(`/runs/${await runId}`);
  const live = page.locator('[data-field="live-result"]');
  await expect(live).toBeVisible({ timeout: 20_000 });
  await expect(live).not.toHaveText("");
  const partial = (await live.textContent()) ?? "";
  await expect(page.locator('[data-field="live-note"]')).toContainText(
    "Being written.",
  );
  await expectNoA11yViolations(page, { extraTags: WCAG_22_AA });
  const outcome = await done;
  expect(outcome.status).toBe("succeeded");
  expect(outcome.durable_deltas).toBe(0);
  expect(partial.length).toBeGreaterThan(0);
  expect(partial.length).toBeLessThan(outcome.content.length);
  expect(outcome.content.startsWith(partial)).toBe(true);
  await expect(page.locator('[data-field="result-text"]')).toBeVisible({
    timeout: 20_000,
  });
  expect(await resultText(page)).toBe(outcome.content);
  await expect(live).toHaveCount(0);
});

test("after the stream is cut while the result is written, the view is rebuilt from the stored artifact", async ({
  page,
  context,
  dbStream,
}) => {
  test.setTimeout(90_000);
  await signIn(page, users.ops);
  const { runId, done } = launch(dbStream, 0.02, 5);
  await page.goto(`/runs/${await runId}`);
  await expect(page.locator('[data-field="live-result"]')).toBeVisible({
    timeout: 20_000,
  });
  // The stream drops mid-result, and the browser reconnects from its cursor.
  await context.setOffline(true);
  // The browser stays offline for 2.5 s, long enough for the stream to drop.
  await page.waitForTimeout(2_500);
  await context.setOffline(false);
  const outcome = await done;
  expect(outcome.status).toBe("succeeded");
  await expect(page.locator('[data-field="result-text"]')).toBeVisible({
    timeout: 30_000,
  });
  expect(await resultText(page)).toBe(outcome.content);
});

test("with Stream text as it's written off, no live text is shown, and the stored result is", async ({
  page,
  dbStream,
}) => {
  test.setTimeout(90_000);
  await page.addInitScript(() =>
    window.localStorage.setItem("autobots.stream", "off"),
  );
  await signIn(page, users.ops);
  await page.goto("/settings");
  await expect(
    page.getByRole("checkbox", { name: "Stream text as it's written" }),
  ).not.toBeChecked();
  const { runId, done } = launch(dbStream, 0.02, 5);
  await page.goto(`/runs/${await runId}`);
  let shown = 0;
  let finished = false;
  // Settled either way, so a helper that fails ends the loop instead of the test's timeout.
  const outcome = done.finally(() => {
    finished = true;
  });
  while (!finished) {
    shown += await page.locator('[data-field="live-result"]').count();
    // Samples the page every 200 ms until the helper ends, so live text shown at any point is counted.
    await page.waitForTimeout(200);
  }
  const stored = await outcome;
  expect(shown).toBe(0);
  await expect(page.locator('[data-field="result-text"]')).toBeVisible({
    timeout: 20_000,
  });
  expect(await resultText(page)).toBe(stored.content);
});
