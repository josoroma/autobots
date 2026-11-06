import { expect, test, type Page } from "@playwright/test";

const EMAIL_A = process.env.AUTOBOTS_TEST_OWNER_EMAIL ?? "";
const PASSWORD_A = process.env.AUTOBOTS_TEST_OWNER_PASSWORD ?? "";
const EMAIL_B = process.env.AUTOBOTS_TEST_OWNER_B_EMAIL ?? "";
const PASSWORD_B = process.env.AUTOBOTS_TEST_OWNER_B_PASSWORD ?? "";

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

// Admission needs a usable key. The last test here removes it, and the settings spec expects none.
async function signInWithKey(page: Page): Promise<void> {
  await signIn(page, EMAIL_A, PASSWORD_A);
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
}

async function write(page: Page, key: string): Promise<Record<string, string>> {
  const token = await (await page.request.get("/api/csrf")).json();
  return {
    [token.header]: token.token,
    Origin: new URL(page.url()).origin,
    "Content-Type": "application/json",
    "Idempotency-Key": key,
  };
}

test("Run admits exactly once through the real form, and a reload starts nothing", async ({
  page,
}) => {
  await signInWithKey(page);
  await page
    .getByRole("textbox", { name: "Goal" })
    .fill("Write the first report");
  const posts: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().endsWith("/api/v1/runs"))
      posts.push(request.url());
  });
  await page.getByRole("button", { name: "Run" }).click();
  const queued = page.locator('[data-outcome="queued"]');
  await expect(queued).toHaveText(/^Your goal is queued\. Open this run$/);
  await expect(
    queued.getByRole("link", { name: "Open this run" }),
  ).toHaveAttribute("href", /^\/runs\/[0-9a-f-]+$/);
  expect(posts).toHaveLength(1);
  await page.reload();
  await page.waitForLoadState("networkidle");
  expect(posts).toHaveLength(1);
});

test("the API returns 202, replays a matching key and refuses different content", async ({
  page,
}) => {
  await signInWithKey(page);
  const data = { goal_text: "Summarize", limit_micro_usd: 1000 };
  const first = await page.request.post("/api/v1/runs", {
    headers: await write(page, "api-key-1"),
    data,
  });
  expect(first.status()).toBe(202);
  const accepted = await first.json();
  expect(accepted.status).toBe("queued");
  expect(accepted.replayed).toBe(false);
  const again = await page.request.post("/api/v1/runs", {
    headers: await write(page, "api-key-1"),
    data,
  });
  expect(again.status()).toBe(202);
  expect((await again.json()).run_id).toBe(accepted.run_id);
  const conflict = await page.request.post("/api/v1/runs", {
    headers: await write(page, "api-key-1"),
    data: { ...data, goal_text: "Different" },
  });
  expect(conflict.status()).toBe(409);
  expect((await conflict.json()).code).toBe("idempotency_conflict");
  const missing = await page.request.post("/api/v1/runs", {
    headers: { ...(await write(page, "x")), "Idempotency-Key": "" },
    data,
  });
  expect(missing.status()).toBe(422);
});

test("commands follow the table through the API, and terminal runs stay closed", async ({
  page,
}) => {
  await signInWithKey(page);
  const admitted = await page.request.post("/api/v1/runs", {
    headers: await write(page, "api-key-2"),
    data: { goal_text: "Commands", limit_micro_usd: 1000 },
  });
  const { run_id: id } = await admitted.json();
  const post = async (name: string, version: number, key: string) =>
    page.request.post(`/api/v1/runs/${id}/${name}`, {
      headers: await write(page, key),
      data: { expected_version: version },
    });
  const paused = await post("pause", 1, "c1");
  expect((await paused.json()).status).toBe("paused");
  const stale = await post("resume", 1, "c2");
  expect(stale.status()).toBe(409);
  expect((await stale.json()).code).toBe("version_conflict");
  const resumed = await post("resume", 2, "c3");
  expect((await resumed.json()).status).toBe("queued");
  const invalid = await page.request.post(`/api/v1/runs/${id}/input`, {
    headers: await write(page, "c4"),
    data: { expected_version: 3, value: "an answer" },
  });
  expect(invalid.status()).toBe(409);
  expect((await invalid.json()).code).toBe("transition_refused");
  const cancelled = await post("cancel", 3, "c5");
  expect((await cancelled.json()).status).toBe("cancelled");
  const reopened = await post("resume", 4, "c6");
  expect(reopened.status()).toBe(409);
  const summary = await (await page.request.get(`/api/v1/runs/${id}`)).json();
  expect(summary.status).toBe("cancelled");
  expect(summary.version).toBe(4);
  expect(JSON.stringify(summary)).not.toContain("lease");
  expect(JSON.stringify(summary)).not.toContain("policy_snapshot");
});

test("another workspace cannot see or command the run", async ({ browser }) => {
  const owner = await (await browser.newContext()).newPage();
  await signInWithKey(owner);
  const admitted = await owner.request.post("/api/v1/runs", {
    headers: await write(owner, "api-key-3"),
    data: { goal_text: "Private", limit_micro_usd: 1000 },
  });
  const { run_id: id } = await admitted.json();
  const other = await (await browser.newContext()).newPage();
  await signIn(other, EMAIL_B, PASSWORD_B);
  expect((await other.request.get(`/api/v1/runs/${id}`)).status()).toBe(404);
  const pause = await other.request.post(`/api/v1/runs/${id}/pause`, {
    headers: await write(other, "foreign"),
    data: { expected_version: 1 },
  });
  expect(pause.status()).toBe(404);
});

test("resume checks readiness, and a finished run takes a linked new run", async ({
  page,
}) => {
  await signInWithKey(page);
  const admitted = await page.request.post("/api/v1/runs", {
    headers: await write(page, "api-key-5"),
    data: { goal_text: "Readiness", limit_micro_usd: 1000 },
  });
  const { run_id: id } = await admitted.json();
  const pause = await page.request.post(`/api/v1/runs/${id}/pause`, {
    headers: await write(page, "r1"),
    data: { expected_version: 1 },
  });
  expect((await pause.json()).status).toBe("paused");
  await page.goto("/settings/models");
  await expect(page.locator('[data-field="auth"]')).toBeVisible();
  await page.getByRole("button", { name: "Disconnect" }).click();
  await expect(page.locator('[data-field="source"]')).toHaveText("None");
  const refused = await page.request.post(`/api/v1/runs/${id}/resume`, {
    headers: await write(page, "r2"),
    data: { expected_version: 2 },
  });
  expect(refused.status()).toBe(409);
  expect((await refused.json()).code).toBe("credentials_required");
  await signInWithKey(page);
  const resumed = await page.request.post(`/api/v1/runs/${id}/resume`, {
    headers: await write(page, "r3"),
    data: { expected_version: 2 },
  });
  expect((await resumed.json()).status).toBe("queued");
  const early = await page.request.post("/api/v1/runs", {
    headers: await write(page, "api-key-6"),
    data: {
      goal_text: "Too early",
      limit_micro_usd: 1000,
      continues_run_id: id,
    },
  });
  expect(early.status()).toBe(409);
  expect((await early.json()).code).toBe("run_not_continuable");
  await page.request.post(`/api/v1/runs/${id}/cancel`, {
    headers: await write(page, "r4"),
    data: { expected_version: 3 },
  });
  const linked = await page.request.post("/api/v1/runs", {
    headers: await write(page, "api-key-7"),
    data: {
      goal_text: "Continue",
      limit_micro_usd: 1000,
      continues_run_id: id,
    },
  });
  expect(linked.status()).toBe(202);
  const reconcile = await page.request.post(
    `/api/v1/runs/${id}/model-calls/reconcile`,
    {
      headers: await write(page, "r5"),
      data: { charged_micro_usd: 5 },
    },
  );
  expect((await reconcile.json()).reconciled_calls).toBe(0);
});

test("a workspace with no key cannot admit a run", async ({ page }) => {
  await signInWithKey(page);
  await page.goto("/settings/models");
  await expect(page.locator('[data-field="auth"]')).toBeVisible();
  await page.getByRole("button", { name: "Disconnect" }).click();
  await expect(page.locator('[data-field="source"]')).toHaveText("None");
  const refused = await page.request.post("/api/v1/runs", {
    headers: await write(page, "no-key"),
    data: { goal_text: "Blocked", limit_micro_usd: 1000 },
  });
  expect(refused.status()).toBe(409);
  expect((await refused.json()).code).toBe("credentials_required");
});
