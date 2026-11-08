import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";

// US-15.24, PRD-Studio ST-01 and Decision 0022 D4. tests/db/result_stream_live.py admits a run in the
// ops-n workspace, prints its ID, waits for the page, then writes its result with a streaming scripted
// model whose pieces are spaced out, and prints the outcome once the result is stored.
const EMAIL = process.env.AUTOBOTS_TEST_OPS_EMAIL ?? "";
const PASSWORD = process.env.AUTOBOTS_TEST_OPS_PASSWORD ?? "";
const WORKSPACE = process.env.AUTOBOTS_TEST_OPS_WORKSPACE ?? "";

type Outcome = {
  run_id: string;
  status: string;
  durable_deltas: number;
  content: string;
};

function launch(
  delay: number,
  wait: number,
): { runId: Promise<string>; done: Promise<Outcome> } {
  const child = spawn(
    process.env.AUTOBOTS_TEST_PYTHON ?? "",
    [
      process.env.AUTOBOTS_TEST_STREAM_HELPER ?? "",
      WORKSPACE,
      String(delay),
      String(wait),
    ],
    {
      env: {
        ...process.env,
        AUTOBOTS_DATABASE_URL: process.env.AUTOBOTS_TEST_RUNTIME_URL ?? "",
        AUTOBOTS_STORAGE_BASE: process.env.AUTOBOTS_TEST_STORAGE_BASE ?? "",
        AUTOBOTS_STORAGE_SERVICE: process.env.AUTOBOTS_TEST_SERVICE_KEY ?? "",
        PYTHONPATH: process.env.AUTOBOTS_TEST_PYTHONPATH ?? "",
      },
      stdio: ["ignore", "pipe", "inherit"],
    },
  );
  const lines = createInterface({ input: child.stdout });
  const seen: string[] = [];
  let first: (id: string) => void = () => undefined;
  let last: (outcome: Outcome) => void = () => undefined;
  const runId = new Promise<string>((resolve) => (first = resolve));
  const done = new Promise<Outcome>((resolve) => (last = resolve));
  lines.on("line", (line) => {
    seen.push(line);
    const parsed = JSON.parse(line) as Partial<Outcome>;
    if (seen.length === 1) first(parsed.run_id ?? "");
    else last(parsed as Outcome);
  });
  return { runId, done };
}

async function signIn(page: Page): Promise<void> {
  await page.goto("/sign-in");
  await page.getByLabel("Email").fill(EMAIL);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText(/Signed in, with access to/)).toBeVisible();
}

const resultText = (page: Page) =>
  page.locator('[data-field="result-text"]').textContent();

test("the result appears while it's written, and then the stored artifact replaces it exactly", async ({
  page,
}) => {
  test.setTimeout(90_000);
  expect(WORKSPACE, "the ops-n workspace is arranged").not.toBe("");
  await signIn(page);
  const { runId, done } = launch(0.02, 5);
  await page.goto(`/runs/${await runId}`);
  const live = page.locator('[data-field="live-result"]');
  await expect(live).toBeVisible({ timeout: 20_000 });
  await expect(live).not.toHaveText("");
  const partial = (await live.textContent()) ?? "";
  await expect(page.locator('[data-field="live-note"]')).toContainText(
    "Being written.",
  );
  const scan = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(scan.violations).toEqual([]);
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
}) => {
  test.setTimeout(90_000);
  await signIn(page);
  const { runId, done } = launch(0.02, 5);
  await page.goto(`/runs/${await runId}`);
  await expect(page.locator('[data-field="live-result"]')).toBeVisible({
    timeout: 20_000,
  });
  // The stream drops mid-result, and the browser reconnects from its cursor.
  await context.setOffline(true);
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
}) => {
  test.setTimeout(90_000);
  await page.addInitScript(() =>
    window.localStorage.setItem("autobots.stream", "off"),
  );
  await signIn(page);
  await page.goto("/settings");
  await expect(
    page.getByRole("checkbox", { name: "Stream text as it's written" }),
  ).not.toBeChecked();
  const { runId, done } = launch(0.02, 5);
  await page.goto(`/runs/${await runId}`);
  let shown = 0;
  let finished = false;
  const outcome = done.then((value) => {
    finished = true;
    return value;
  });
  while (!finished) {
    shown += await page.locator('[data-field="live-result"]').count();
    await page.waitForTimeout(200);
  }
  expect(shown).toBe(0);
  await expect(page.locator('[data-field="result-text"]')).toBeVisible({
    timeout: 20_000,
  });
  expect(await resultText(page)).toBe((await outcome).content);
});
