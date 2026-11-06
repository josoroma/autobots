import { readFileSync } from "node:fs";

import { expect, test, type Page } from "@playwright/test";

const EMAIL_A = process.env.AUTOBOTS_TEST_OWNER_EMAIL ?? "";
const PASSWORD_A = process.env.AUTOBOTS_TEST_OWNER_PASSWORD ?? "";
const EMAIL_E = process.env.AUTOBOTS_TEST_FILES_EMAIL ?? "";
const PASSWORD_E = process.env.AUTOBOTS_TEST_FILES_PASSWORD ?? "";
const KEYLESS_RUN = process.env.AUTOBOTS_TEST_FILES_RUN ?? "";
const WAITING_RUN = process.env.AUTOBOTS_TEST_WAITING_RUN ?? "";

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

async function write(page: Page, key: string): Promise<Record<string, string>> {
  const token = await (await page.request.get("/api/csrf")).json();
  return {
    [token.header]: token.token,
    Origin: new URL(page.url()).origin,
    "Content-Type": "application/json",
    "Idempotency-Key": key,
  };
}

async function ensureKey(page: Page): Promise<void> {
  await page.goto("/settings/models");
  const source = page.locator('[data-field="source"]');
  await expect(source).toBeVisible();
  if ((await source.textContent())?.trim() === "None") {
    await page
      .getByLabel(/API key|Replace key/)
      .fill("sk-or-valid-arranged-closure");
    await page.getByRole("button", { name: "Save & validate" }).click();
    await expect(page.locator('[data-field="auth"]')).toHaveText(
      "The key authenticated.",
    );
  }
}

const finished = (page: Page, status: string) =>
  expect(page.locator("[data-run-status]")).toHaveAttribute(
    "data-run-status",
    status,
    { timeout: 60_000 },
  );

test("the goal and its criteria read the same after a compaction as before it", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await signIn(page, EMAIL_A, PASSWORD_A);
  await ensureKey(page);
  await page.goto("/");
  const stamp = Date.now();
  const goal = `slice-compact-${stamp}: keep this goal whole`;
  const criterion = "The report states the total";
  const reply = await page.request.post("/api/v1/runs", {
    headers: await write(page, `compact-${stamp}`),
    data: { goal_text: goal, acceptance_criteria: [criterion] },
  });
  expect(reply.status()).toBe(202);
  const id = (await reply.json()).run_id;
  await page.goto(`/runs/${id}`);
  const main = page.locator("main");
  await expect(main).toContainText(goal);
  await expect(main).toContainText(criterion);
  await finished(page, "succeeded");
  await page.reload();
  await expect(main).toContainText(goal);
  await expect(main).toContainText(criterion);
  // Compaction really happened: it's on the ledger under its own role.
  const inspector = await (
    await page.request.get(`/api/v1/runs/${id}/inspector`)
  ).json();
  expect(
    inspector.model_calls.filter(
      (call: { role: string }) => call.role === "summarizer",
    ).length,
  ).toBeGreaterThan(0);
});

test("the Assignments card shows a child's Expert and outcome, and each run links to the other", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await signIn(page, EMAIL_A, PASSWORD_A);
  await ensureKey(page);
  await page.goto("/");
  const stamp = Date.now();
  const tools = ["calculate", "save_artifact", "publish_artifact"];
  const expert = async (name: string): Promise<string> =>
    (
      await (
        await page.request.post("/api/v1/experts", {
          headers: await write(page, `${name}-${stamp}`),
          data: { name: `${name} ${stamp}`, config: { tools } },
        })
      ).json()
    ).id;
  const lead = await expert("Closure lead");
  const helper = await expert("Closure helper");
  const session = await (
    await page.request.post("/api/v1/sessions", {
      headers: await write(page, `closure-session-${stamp}`),
      data: {
        kind: "coordinator",
        experts: [{ expert_id: lead }, { expert_id: helper }],
      },
    })
  ).json();
  const reply = await page.request.post("/api/v1/runs", {
    headers: await write(page, `closure-run-${stamp}`),
    data: {
      goal_text: `slice-delegate expert=${helper}`,
      session_id: session.id,
      expert_id: lead,
    },
  });
  expect(reply.status()).toBe(202);
  const id = (await reply.json()).run_id;
  await page.goto(`/runs/${id}`);
  const card = page.getByRole("region", { name: "Assignments" });
  const item = card.locator('[data-assignment="finished"]');
  await expect(item).toBeVisible({ timeout: 60_000 });
  await expect(item).toContainText(`Closure helper ${stamp}`);
  await expect(item).toContainText("succeeded");
  await item.getByRole("link").click();
  await expect(page).not.toHaveURL(new RegExp(id));
  await finished(page, "succeeded");
  const parent = page.locator('[data-field="parent-run"]');
  await expect(parent.getByRole("link")).toHaveAttribute("href", `/runs/${id}`);
});

test("a run's plan, approval, artifact and status come back after the connection drops", async ({
  page,
}) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
  await page.goto(`/runs/${WAITING_RUN}`);
  await expect(page.locator("[data-run-status]")).toHaveAttribute(
    "data-run-status",
    "waiting_approval",
  );
  const main = page.locator("main");
  await expect(main.locator("[data-task-status]")).toHaveCount(1);
  await expect(main).toContainText("Write the report");
  await expect(main.locator("[data-artifact-status]")).toHaveCount(1);
  await expect(main).toContainText("Approval requested for send_blind");
  await expect(page.locator("[data-connection]")).toHaveAttribute(
    "data-connection",
    "live",
  );
  const before = await main.locator("[data-sequence]").count();
  // A real loss of the network for this page. The command goes through Node, so it commits meanwhile.
  await page.context().setOffline(true);
  await expect(page.locator("[data-connection]")).toHaveAttribute(
    "data-connection",
    "reconnecting",
    { timeout: 15_000 },
  );
  const summary = await (
    await page.request.get(`/api/v1/runs/${WAITING_RUN}`)
  ).json();
  const cancelled = await page.request.post(
    `/api/v1/runs/${WAITING_RUN}/cancel`,
    {
      headers: await write(page, `closure-cancel-${Date.now()}`),
      data: { expected_version: summary.version },
    },
  );
  expect(cancelled.status()).toBe(200);
  await page.context().setOffline(false);
  await expect(page.locator("[data-run-status]")).not.toHaveAttribute(
    "data-run-status",
    "waiting_approval",
    { timeout: 20_000 },
  );
  await expect(main.locator("[data-task-status]")).toHaveCount(1);
  await expect(main.locator("[data-artifact-status]")).toHaveCount(1);
  await expect(main).toContainText("Approval requested for send_blind");
  // Every event in order, with no gap or duplicate.
  await expect
    .poll(() => main.locator("[data-sequence]").count(), { timeout: 20_000 })
    .toBeGreaterThan(before);
  const sequences = await main
    .locator("[data-sequence]")
    .evaluateAll((items) =>
      items.map((item) => Number(item.getAttribute("data-sequence"))),
    );
  const ordered = [...sequences].sort((a, b) => a - b);
  expect(new Set(sequences).size).toBe(sequences.length);
  expect(ordered).toEqual(
    ordered.map((_, index) => (ordered[0] as number) + index),
  );
});

test("with no key, a run's artifacts can be listed and downloaded, and inference is refused", async ({
  page,
}) => {
  await signIn(page, EMAIL_E, PASSWORD_E);
  const status = await (
    await page.request.get("/api/settings/model-providers")
  ).json();
  expect(status.source).toBe("none");
  await page.goto(`/runs/${KEYLESS_RUN}`);
  const artifact = page.locator('[data-artifact-status="published"]');
  await expect(artifact).toContainText("report");
  const href = await artifact.getByRole("link").first().getAttribute("href");
  const download = await page.request.get(href ?? "");
  expect(download.status()).toBe(200);
  expect(await download.text()).toContain("Total: 5");
  const refused = await page.request.post("/api/v1/runs", {
    headers: await write(page, `keyless-${Date.now()}`),
    data: { goal_text: "needs a model" },
  });
  expect(refused.status()).toBe(409);
  expect((await refused.json()).code).toBe("credentials_required");
  // The whole suite's fake upstream log is checked for chat calls once it ends.
  const log = readFileSync(
    process.env.AUTOBOTS_TEST_UPSTREAM_LOG ?? "",
    "utf8",
  );
  expect(log).not.toContain("chat/completions");
});
