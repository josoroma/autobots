import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const EMAIL_A = process.env.AUTOBOTS_TEST_OWNER_EMAIL ?? "";
const PASSWORD_A = process.env.AUTOBOTS_TEST_OWNER_PASSWORD ?? "";
const EMAIL_B = process.env.AUTOBOTS_TEST_OWNER_B_EMAIL ?? "";
const PASSWORD_B = process.env.AUTOBOTS_TEST_OWNER_B_PASSWORD ?? "";
const LOOP_RUN = process.env.AUTOBOTS_TEST_LOOP_RUN ?? "";
const GAP_RUN = process.env.AUTOBOTS_TEST_ARTIFACT_RUN ?? "";

async function signIn(
  page: Page,
  email: string,
  password: string,
): Promise<void> {
  await page.goto("/sign-in");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText(/Signed in, with access to/)).toBeVisible();
}

async function headers(
  page: Page,
  key: string,
): Promise<Record<string, string>> {
  const token = await (await page.request.get("/api/csrf")).json();
  return {
    [token.header]: token.token,
    Origin: new URL(page.url()).origin,
    "Content-Type": "application/json",
    "Idempotency-Key": key,
  };
}

async function admitted(page: Page, label: string): Promise<string> {
  await page.goto("/settings/models");
  const source = page.locator('[data-field="source"]');
  await expect(source).toBeVisible();
  if ((await source.textContent())?.trim() === "None") {
    await page
      .getByLabel(/API key|Replace key/)
      .fill("sk-or-valid-arranged-first");
    await page.getByRole("button", { name: "Save & validate" }).click();
    await expect(page.locator('[data-field="auth"]')).toHaveText(
      "The key authenticated.",
    );
  }
  await page.goto("/");
  const reply = await page.request.post("/api/v1/runs", {
    headers: await headers(page, `workspace-${label}`),
    data: { goal_text: `Goal ${label}`, limit_micro_usd: 1000 },
  });
  expect(reply.status()).toBe(202);
  return (await reply.json()).run_id;
}

async function command(
  page: Page,
  id: string,
  name: string,
  version: number,
  key: string,
) {
  return page.request.post(`/api/v1/runs/${id}/${name}`, {
    headers: await headers(page, key),
    data: { expected_version: version },
  });
}

async function disconnectKey(page: Page): Promise<void> {
  await page.goto("/settings/models");
  await expect(page.locator('[data-field="auth"]')).toBeVisible();
  await page.getByRole("button", { name: "Disconnect" }).click();
  await expect(page.locator('[data-field="source"]')).toHaveText("None");
}

test("events arrive live and survive a dropped connection without duplicates", async ({
  page,
}) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
  const id = await admitted(page, "live");
  await page.goto(`/runs/${id}`);
  await expect(page.locator("[data-run-status]")).toHaveAttribute(
    "data-run-status",
    "queued",
  );
  await expect(page.locator("[data-connection]")).toHaveAttribute(
    "data-connection",
    "live",
  );

  expect((await command(page, id, "pause", 1, "l1")).status()).toBe(200);
  await expect(page.locator("[data-run-status]")).toHaveAttribute(
    "data-run-status",
    "paused",
  );
  await expect(page.locator('[data-sequence="2"]')).toContainText(
    "queued to paused",
  );

  // The stream ends on its own, as a dropped connection does, and now nothing can reconnect.
  await page.route("**/api/v1/runs/**", (route) => route.abort());
  await expect(page.locator("[data-connection]")).toHaveAttribute(
    "data-connection",
    "reconnecting",
    { timeout: 10_000 },
  );
  // These go through Node, not the page, so they happen while it is disconnected.
  expect((await command(page, id, "resume", 2, "l2")).status()).toBe(200);
  expect((await command(page, id, "pause", 3, "l3")).status()).toBe(200);
  await expect(page.locator("[data-run-status]")).toHaveAttribute(
    "data-run-status",
    "paused",
  );
  await expect(page.locator('[data-sequence="4"]')).toHaveCount(0);

  await page.unroute("**/api/v1/runs/**");
  await expect(page.locator("[data-connection]")).toHaveAttribute(
    "data-connection",
    "live",
    { timeout: 15_000 },
  );
  await expect(page.locator('[data-sequence="4"]')).toContainText(
    "queued to paused",
  );
  const sequences = await page
    .locator("[data-sequence]")
    .evaluateAll((items) =>
      items.map((item) => item.getAttribute("data-sequence")),
    );
  expect(sequences).toEqual(["1", "2", "3", "4"]);

  await page.reload();
  await expect(page.locator("[data-sequence]")).toHaveCount(4);
  await expect(page.locator("[data-run-status]")).toHaveAttribute(
    "data-run-status",
    "paused",
  );
});

test("closing the page does not change the run, and the end of a run ends the stream", async ({
  browser,
}) => {
  const context = await browser.newContext();
  const page = await context.newPage();
  await signIn(page, EMAIL_A, PASSWORD_A);
  const id = await admitted(page, "closing");
  const viewer = await context.newPage();
  await viewer.goto(`/runs/${id}`);
  await expect(viewer.locator("[data-connection]")).toHaveAttribute(
    "data-connection",
    "live",
  );
  await viewer.close();
  const summary = await (await page.request.get(`/api/v1/runs/${id}`)).json();
  expect(summary.status).toBe("queued");
  expect(summary.version).toBe(1);
  const again = await context.newPage();
  await again.goto(`/runs/${id}`);
  await expect(again.locator("[data-connection]")).toHaveAttribute(
    "data-connection",
    "live",
  );
  expect((await command(page, id, "cancel", 1, "c1")).status()).toBe(200);
  await expect(again.locator("[data-run-status]")).toHaveAttribute(
    "data-run-status",
    "cancelled",
  );
  await expect(again.locator("[data-connection]")).toHaveAttribute(
    "data-connection",
    "ended",
    { timeout: 10_000 },
  );
  await context.close();
});

test("a plan, its evidence, a reason and artifacts show, sanitized, in both themes", async ({
  page,
}) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
  await page.goto(`/runs/${LOOP_RUN}`);
  await expect(page.locator("[data-run-status]")).toHaveAttribute(
    "data-run-status",
    "failed",
  );
  await expect(page.locator("[data-stop-reason]")).toHaveText(
    /plan incomplete/,
  );
  await expect(page.getByText("Has a summary")).toBeVisible();
  await expect(page.locator('[data-task-status="complete"]')).toContainText(
    "[redacted]",
  );
  await expect(
    page.locator('[data-artifact-status="published"]'),
  ).toContainText("loop.md");
  await expect(page.locator("[data-connection]")).toHaveAttribute(
    "data-connection",
    "ended",
    { timeout: 15_000 },
  );

  const html = await page.content();
  for (const leak of [
    "sk-or-leaked",
    "PROTECTED-REASONING",
    "checkpoint",
    "object_path",
    "policy_snapshot",
  ]) {
    expect(html).not.toContain(leak);
  }
  const replay = await (
    await page.request.get(`/api/v1/runs/${LOOP_RUN}/events?after=0`)
  ).text();
  expect(replay).not.toContain("PROTECTED-REASONING");
  const workspace = await (
    await page.request.get(`/api/v1/runs/${LOOP_RUN}/workspace`)
  ).text();
  expect(workspace).not.toContain("sk-or-leaked");
  expect(workspace).not.toContain("lease");

  for (const scheme of ["dark", "light"] as const) {
    await page.evaluate(
      (theme) => localStorage.setItem("autobots.theme", theme),
      scheme,
    );
    await page.reload();
    await expect(page.locator("[data-run-status]")).toBeVisible();
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(results.violations.map((violation) => violation.id)).toEqual([]);
  }
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to content" }),
  ).toBeFocused();
});

test("retained events that can't fill the range say so, and the status comes from the snapshot", async ({
  page,
}) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
  const page1 = await (
    await page.request.get(`/api/v1/runs/${GAP_RUN}/events?after=0`)
  ).json();
  expect(page1.gap).toBe(true);
  await page.goto(`/runs/${GAP_RUN}`);
  await expect(page.locator("[data-gap]")).toBeVisible();
  await expect(page.locator("[data-run-status]")).toBeVisible();
  await expect(page.locator('[data-sequence="1"]')).toHaveCount(0);
  await expect(page.locator('[data-sequence="3"]')).toContainText("published");
});

test("another workspace gets a clear refusal", async ({ page }) => {
  await signIn(page, EMAIL_B, PASSWORD_B);
  await page.goto(`/runs/${LOOP_RUN}`);
  await expect(page.locator('[data-state="unavailable"]')).toBeVisible();
  expect(
    (
      await page.request.get(`/api/v1/runs/${LOOP_RUN}/events?after=0`)
    ).status(),
  ).toBe(404);
  expect(
    (
      await page.request.get(`/api/v1/runs/${LOOP_RUN}/events/stream?after=0`)
    ).status(),
  ).toBe(404);
  expect(
    (await page.request.get(`/api/v1/runs/${LOOP_RUN}/workspace`)).status(),
  ).toBe(404);
});

test("a signed-out stream is refused, and Run links to the new run", async ({
  page,
  request,
}) => {
  expect(
    (await request.get(`/api/v1/runs/${LOOP_RUN}/events/stream`)).status(),
  ).toBe(401);
  await signIn(page, EMAIL_A, PASSWORD_A);
  await admitted(page, "link");
  await page.getByRole("textbox", { name: "Goal" }).fill("Open what I started");
  await page.getByRole("button", { name: "Run" }).click();
  await page.getByRole("link", { name: "Open this run" }).click();
  await expect(page).toHaveURL(/\/runs\//);
  await expect(
    page.getByRole("region", { name: "Goal" }).getByRole("paragraph"),
  ).toHaveText("Open what I started");
  // The settings spec, which runs after this one, expects no key.
  await disconnectKey(page);
});
