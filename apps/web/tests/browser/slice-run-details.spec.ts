import {
  parseExpertView,
  parseModelPolicyState,
  parseRunList,
  parseSessionView,
  parseWorkflowView,
} from "@autobots/api-client";
import type { Page } from "@playwright/test";

import { expectRefusal, getJson, send, writeHeaders } from "./support/api.ts";
import { signIn, users } from "./support/auth.ts";
import { inToOut, twoCountsRun, WorkerScenario } from "./support/builders.ts";
import { expect, test } from "./support/fixtures.ts";
import { ensureProviderKey } from "./support/keys.ts";
import { expectNoPrivateValues } from "./support/leaks.ts";
import { admitRun, cancelUnlessTerminal, readRun } from "./support/runs.ts";

// What a run discloses, freezes and reports. Its name puts it with the slice suites.
const TERRA = "openrouter_terra";
const DEEPSEEK = "openrouter_deepseek_flash";
const TERRA_CANONICAL = "openai/gpt-6.1-terra-20261026";
const DATA =
  "selected instructions, conversation and context excerpts, retrieved material, tool outputs and required protocol metadata";

function policy(page: Page) {
  return getJson(page, {
    path: "/api/settings/model-policy",
    parse: parseModelPolicyState,
  });
}

async function expectDisclosure(page: Page, model: string): Promise<void> {
  const disclosure = page.locator('[data-field="disclosure"]');
  await expect(disclosure.locator('[data-disclosure="model"]')).toContainText(
    model,
  );
  await expect(disclosure.locator('[data-disclosure="budget"]')).toContainText(
    "US$1.00",
  );
  await expect(disclosure.locator('[data-disclosure="data"]')).toContainText(
    DATA,
  );
  await expect(disclosure.locator('[data-disclosure="consent"]')).toHaveText(
    "Nothing is sent until you press Run.",
  );
  await disclosure.locator("summary").click();
  const roles = disclosure.locator('[data-disclosure="roles"] li');
  await expect(roles).toHaveCount(14);
  await expect(roles.filter({ hasText: "executor" })).toContainText(model);
}

test("each screen that creates a run says what it uses, sends and spends, and sends nothing first", async ({
  page,
}) => {
  await signIn(page, users.owner);
  await ensureProviderKey(page);
  const created: string[] = [];
  page.on("request", (request) => {
    const url = request.url();
    if (
      request.method() === "POST" &&
      (url.endsWith("/api/v1/runs") || url.endsWith("/executions"))
    ) {
      created.push(url);
    }
  });

  await page.goto("/");
  await expectDisclosure(page, TERRA_CANONICAL);

  // An Expert's session.
  const expert = await send(page, {
    path: "/api/v1/experts",
    key: `disclose-expert-${Date.now()}`,
    data: { name: `Disclosing ${Date.now()}`, config: {} },
    status: 201,
    parse: parseExpertView,
  });
  const session = await send(page, {
    path: "/api/v1/sessions",
    key: `disclose-session-${Date.now()}`,
    data: { kind: "direct", experts: [{ expert_id: expert.id }] },
    status: 201,
    parse: parseSessionView,
  });
  await page.goto(`/sessions/${session.id}`);
  await expectDisclosure(page, TERRA_CANONICAL);

  // A workflow's run.
  const workflow = await send(page, {
    path: "/api/v1/workflows",
    key: `disclose-workflow-${Date.now()}`,
    data: { name: `Disclosing ${Date.now()}` },
    status: 201,
    parse: parseWorkflowView,
  });
  const published = await page.request.post(
    `/api/v1/workflows/${workflow.id}/versions`,
    {
      headers: await writeHeaders(page, `disclose-version-${Date.now()}`),
      data: { expected_version: 0, graph: inToOut() },
    },
  );
  expect(published.status()).toBeLessThan(300);
  await page.goto(`/workflows/${workflow.id}`);
  await expectDisclosure(page, TERRA_CANONICAL);
  await expect(page.locator('[data-disclosure="data"]')).toContainText(
    "if an agent step runs",
  );
  expect(created).toEqual([]);
});

test("a person picks the other model for one run: it freezes, the default stays, and the workspace says what dispatches", async ({
  page,
}) => {
  await signIn(page, users.owner);
  await ensureProviderKey(page);
  const before = await policy(page);
  expect(before.default_profile).toBe(TERRA);
  await page.goto("/");
  await expect(
    page
      .getByLabel("Model for this run")
      .locator(`option[value="${DEEPSEEK}"]`),
  ).toHaveCount(0);
  await page.getByLabel("Model for this run").selectOption(TERRA);
  await expectDisclosure(page, TERRA_CANONICAL);
  await page
    .getByRole("textbox", { name: "Goal" })
    .fill(`${WorkerScenario.onlyClaims} one run`);
  await page.getByRole("button", { name: "Run", exact: true }).click();
  const link = page
    .locator('[data-outcome="queued"]')
    .getByRole("link", { name: "Open this run" });
  await expect(link).toBeVisible();
  await link.click();
  const map = page.locator('[data-field="role-map"]');
  await expect(map.locator("li")).toHaveCount(14);
  for (const item of await map.locator("li").all()) {
    await expect(item).toContainText(TERRA_CANONICAL);
  }
  await expect(map).toContainText(
    "Only the executor's binding dispatches in this release",
  );
  const after = await policy(page);
  expect(after.default_profile).toBe(TERRA);
  expect(after.version).toBe(before.version);
  await cancelUnlessTerminal(page, page.url().split("/").pop() ?? "");
});

test("the workspace shows budgets, and the inspector shows reported and estimated costs apart, errors and evidence", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await signIn(page, users.owner);
  await ensureProviderKey(page);
  await page.goto("/");
  const id = await admitRun(
    page,
    twoCountsRun(`${WorkerScenario.failedCall} ${WorkerScenario.reasoned}`),
    { key: `slice-failed-call-${Date.now()}` },
  );
  await page.goto(`/runs/${id}`);
  await expect(page.locator("[data-run-status]")).toHaveAttribute(
    "data-run-status",
    "succeeded",
    { timeout: 60_000 },
  );
  const budgets = page.locator('[data-field="budgets"]');
  await expect(budgets).toContainText("512 output tokens per call");
  await expect(budgets).toContainText("8K tokens of context");
  await expect(budgets).toContainText("Spend limit: US$1.00");

  await page.getByRole("link", { name: "Inspect this run" }).click();
  const failed = page.locator('[data-call="failed_before_acceptance"]').first();
  await expect(failed).toContainText("Error: provider error");
  await expect(failed.locator('[data-cost="reported"]')).toHaveText(
    "Reported charge: US$0.00",
  );
  await expect(failed.locator('[data-cost="estimated"]')).toContainText(
    "Estimated worst case, not a charge:",
  );
  const settled = page.locator('[data-call="succeeded"]').first();
  await expect(settled.locator('[data-cost="reported"]')).toContainText(
    "Reported charge: US$0.0001",
  );
  const evidence = page.locator('[data-field="evidence"]');
  await expect(evidence).toContainText("Reported the total of the two counts");
  const link = evidence.getByRole("link", { name: "outputs/report.md" });
  const download = await page.request.get(
    (await link.getAttribute("href")) ?? "",
  );
  expect(await download.text()).toContain("Total: 5");
  const body = await (
    await page.request.get(`/api/v1/runs/${id}/inspector`)
  ).text();
  expectNoPrivateValues(body, { label: "the inspector's reply" });
  expectNoPrivateValues(await page.locator("main").innerText(), {
    label: "the inspector",
  });
});

test("an unapproved model is refused, no run starts, and the draft is kept", async ({
  page,
}) => {
  await signIn(page, users.owner);
  await ensureProviderKey(page);
  await page.goto("/");
  const listed = async () =>
    (await getJson(page, { path: "/api/v1/runs", parse: parseRunList })).runs
      .length;
  const before = await listed();
  const draft = "A draft that must survive";
  await page.getByRole("textbox", { name: "Goal" }).fill(draft);
  // The picker only offers approved models, so the request is changed on its way, and the server decides.
  await page.route("**/api/v1/runs", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    const body = route.request().postDataJSON();
    return route.continue({
      postData: JSON.stringify({ ...body, run_profile: "openai/gpt-unknown" }),
    });
  });
  await page.getByRole("button", { name: "Run", exact: true }).click();
  await expect(page.locator('[data-outcome="model_refused"]')).toContainText(
    "isn't approved",
  );
  await page.unroute("**/api/v1/runs");
  await expect(page.getByRole("textbox", { name: "Goal" })).toHaveValue(draft);
  expect(await listed()).toBe(before);
  const direct = await page.request.post("/api/v1/runs", {
    headers: await writeHeaders(page, `refused-${Date.now()}`),
    data: { goal_text: "No", run_profile: "openrouter_astra" },
  });
  expect(direct.status()).toBe(422);
  expect(await listed()).toBe(before);
  await page.getByRole("textbox", { name: "Goal" }).fill("");
});

test("reusing a key with a model chosen is a conflict, not a replay of the first", async ({
  page,
}) => {
  await signIn(page, users.owner);
  await ensureProviderKey(page);
  await page.goto("/");
  const key = `same-key-${Date.now()}`;
  const goal = `${WorkerScenario.onlyClaims} keyed`;
  await admitRun(page, { goal_text: goal }, { key });
  const other = await page.request.post("/api/v1/runs", {
    headers: await writeHeaders(page, key),
    data: { goal_text: goal, run_profile: TERRA },
  });
  await expectRefusal(other, { status: 409, code: "idempotency_conflict" });
});

test("continuing a finished run asks for a new run naming it, with the disclosure, and it stays as it was", async ({
  page,
}) => {
  test.setTimeout(90_000);
  await signIn(page, users.owner);
  await ensureProviderKey(page);
  await page.goto("/");
  const id = await admitRun(
    page,
    { goal_text: `${WorkerScenario.onlyClaims} to continue` },
    { key: `continue-${Date.now()}` },
  );
  await page.goto(`/runs/${id}`);
  await expect(page.locator("[data-run-status]")).toHaveAttribute(
    "data-run-status",
    "failed",
    { timeout: 60_000 },
  );
  const before = await readRun(page, id);
  await page.getByRole("button", { name: "Continue in a new run" }).click();
  await expect(page.locator("[data-continue-run]")).toContainText(
    "it can repeat what this run did",
  );
  await expect(page.locator('[data-disclosure="budget"]')).toContainText(
    "US$1.00",
  );
  // The API commits, and the reply is lost on the way back.
  let firstKey = "";
  await page.route("**/api/v1/runs", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    firstKey = route.request().headers()["idempotency-key"] ?? "";
    await route.fetch();
    return route.fulfill({ status: 503, body: "{}" });
  });
  await page
    .locator("[data-continue-run]")
    .getByRole("button", { name: "Run", exact: true })
    .click();
  await expect(page.locator("[data-continue-run]")).toContainText(
    "it may have started",
  );
  // The same key has to carry the same body, so the model can't change now.
  await expect(
    page.locator("[data-continue-run]").getByLabel("Model for this run"),
  ).toHaveCount(0);
  await page.unroute("**/api/v1/runs");
  const sent = page.waitForRequest(
    (request) =>
      request.method() === "POST" && request.url().endsWith("/api/v1/runs"),
  );
  await page
    .locator("[data-continue-run]")
    .getByRole("button", { name: "Run", exact: true })
    .click();
  // The server repeats what it stored, as the page's copy is cut and redacted.
  const body = (await sent).postDataJSON();
  expect(body.continues_run_id).toBe(id);
  expect(body.goal_text).toBeUndefined();
  // The same key, so pressing again started nothing new, and the page says so.
  expect((await sent).headers()["idempotency-key"]).toBe(firstKey);
  await expect(page.locator("[data-continue-run]")).toContainText(
    "It had already started",
  );
  const link = page.getByRole("link", { name: "Open the run" });
  await expect(link).toBeVisible();
  const href = await link.getAttribute("href");
  expect(href).not.toContain(id);
  const after = await readRun(page, id);
  expect(after.status).toBe("failed");
  expect(after.version).toBe(before.version);
  await page.goto(href ?? "");
  await expect(
    page.getByText(`${WorkerScenario.onlyClaims} to continue`).first(),
  ).toBeVisible();
});

test("a refusal clears the key to continue with, and a refusal after a lost reply keeps it", async ({
  page,
}) => {
  test.setTimeout(90_000);
  await signIn(page, users.owner);
  await ensureProviderKey(page);
  await page.goto("/");
  const id = await admitRun(
    page,
    { goal_text: `${WorkerScenario.onlyClaims} keys` },
    { key: `continue-keys-${Date.now()}` },
  );
  await page.goto(`/runs/${id}`);
  await expect(page.locator("[data-run-status]")).toHaveAttribute(
    "data-run-status",
    "failed",
    { timeout: 60_000 },
  );
  await page.getByRole("button", { name: "Continue in a new run" }).click();
  const run = page.locator("[data-continue-run]").getByRole("button", {
    name: "Run",
  });
  const keys: string[] = [];
  // Each refusal carries the service's error envelope, so it reads as refused, not unknown.
  const refusal = (message: string) => ({
    status: 409,
    contentType: "application/json",
    body: JSON.stringify({ code: "arranged", message }),
  });
  const answers = [
    refusal("Arranged refusal."),
    { status: 503, body: "{}" },
    refusal("Arranged again."),
    refusal("And again."),
  ];
  await page.route("**/api/v1/runs", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    keys.push(route.request().headers()["idempotency-key"] ?? "");
    return route.fulfill(
      answers[keys.length - 1] ?? { status: 500, body: "{}" },
    );
  });
  await run.click();
  await expect(page.getByText("Arranged refusal.")).toBeVisible();
  await run.click();
  await expect(page.getByText(/it may have started/)).toBeVisible();
  expect(keys[1]).not.toBe(keys[0]);
  // A refusal of the resent request doesn't show the first press failed, and says so.
  await run.click();
  await expect(page.getByText("Arranged again.")).toBeVisible();
  await expect(page.getByText(/may still have gone through/)).toBeVisible();
  await run.click();
  await expect(page.getByText("And again.")).toBeVisible();
  // Once the outcome is unknown, no refusal proves nothing started under that key.
  expect(keys[2]).toBe(keys[1]);
  expect(keys[3]).toBe(keys[1]);
  await page.unroute("**/api/v1/runs");
});
