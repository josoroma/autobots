import { parseProviderStatus, parseRunInspector } from "@autobots/api-client";
import type { Page, Route } from "@playwright/test";

import { expectNoA11yViolations } from "./support/a11y.ts";
import { getJson } from "./support/api.ts";
import { signIn, users } from "./support/auth.ts";
import { twoCountsRun, WorkerScenario } from "./support/builders.ts";
import { need } from "./support/env.ts";
import { expect, test } from "./support/fixtures.ts";
import { ensureProviderKey } from "./support/keys.ts";
import { expectNoPrivateValues } from "./support/leaks.ts";
import { admitRun, readRun } from "./support/runs.ts";

// The run list and inspector, in the slice project, with the scripted worker running.
const TERRA = "openai/gpt-6.1-terra-20261026";
const noKeyRun = () => need("AUTOBOTS_TEST_NO_KEY_RUN");

/** Admits the two-counts run for `scenario` from Home, and waits on its page for it to succeed. */
async function finishedRun(page: Page, scenario: string): Promise<string> {
  await page.goto("/");
  const id = await admitRun(page, twoCountsRun(scenario), {
    key: `${scenario}-${Date.now()}`,
  });
  await page.goto(`/runs/${id}`);
  await expect(page.locator("[data-run-status]")).toHaveAttribute(
    "data-run-status",
    "succeeded",
    { timeout: 60_000 },
  );
  return id;
}

test("the run list shows only this workspace's runs, with no key, and starts nothing", async ({
  page,
}) => {
  const keyless = noKeyRun();
  await signIn(page, users.noKey);
  const status = await getJson(page, {
    path: "/api/settings/model-providers",
    parse: parseProviderStatus,
  });
  expect(status.source).toBe("none");
  const posted: string[] = [];
  page.on("request", (request) => {
    if (request.method() !== "GET" && request.url().includes("/runs")) {
      posted.push(request.url());
    }
  });
  await page.goto("/");
  await page.getByRole("link", { name: "Runs" }).click();
  await expect(page.getByRole("heading", { name: "Runs" })).toBeVisible();
  const items = page.locator("[data-run]");
  await expect(items).toHaveCount(1);
  await expect(items.first()).toHaveAttribute("data-run", keyless);
  await expect(items.first()).toContainText("Queued");
  await expect(items.first()).toContainText(
    "Arranged in a workspace with no key",
  );
  await expect(items.first().getByRole("link")).toHaveAttribute(
    "href",
    `/runs/${keyless}`,
  );
  await page.reload();
  await expect(items).toHaveCount(1);
  expect(posted).toEqual([]);
  const after = await readRun(page, keyless);
  expect(after.status).toBe("queued");
  expect(after.version).toBe(1);
  await expectNoA11yViolations(page);
});

test("the inspector shows what a finished run used, attempted and saved, and nothing private", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await signIn(page, users.owner);
  await ensureProviderKey(page);
  const id = await finishedRun(page, WorkerScenario.reasoned);
  await page.getByRole("link", { name: "Inspect this run" }).click();
  await expect(
    page.getByRole("heading", { name: "Run inspector" }),
  ).toBeVisible();
  const reply = await page.request.get(`/api/v1/runs/${id}/inspector`);
  expect(reply.status()).toBe(200);
  const body = await reply.text();
  const view = parseRunInspector(JSON.parse(body));
  expect(view.model_calls.length).toBeGreaterThan(5);
  expect(view.tool_attempts.length).toBeGreaterThan(3);
  expect(view.checkpoints.length).toBeGreaterThan(5);
  const calls = page.locator("[data-call]");
  await expect(calls).toHaveCount(view.model_calls.length);
  await expect(calls.first()).toContainText("executor, attempt 1: succeeded");
  await expect(calls.first()).toContainText("Provider openrouter");
  await expect(calls.first().locator("[data-canonical]")).toHaveText(TERRA);
  await expect(calls.first().locator("[data-wire]")).toHaveText(
    "fixture/model",
  );
  await expect(calls.first().locator("[data-upstream]")).toHaveText("unknown");
  await expect(calls.first()).toContainText("Tokens:");
  for (const tool of ["propose_plan", "save_artifact", "publish_artifact"]) {
    await expect(page.locator(`[data-tool="${tool}"]`).first()).toContainText(
      "succeeded",
    );
  }
  await expect(page.locator("[data-checkpoint]")).toHaveCount(
    view.checkpoints.length,
  );
  // The artifact's content stays in the artifact.
  const extra = ["Total: 5"];
  expectNoPrivateValues(body, { label: "the inspector's reply", extra });
  expectNoPrivateValues(await page.locator("main").innerText(), {
    label: "the inspector",
    extra,
  });
  await expectNoA11yViolations(page);
});

test("another workspace's run is refused, on the route and on the screen", async ({
  page,
  signedInPage,
}) => {
  test.setTimeout(120_000);
  await signIn(page, users.owner);
  await ensureProviderKey(page);
  // A goal with no scenario word, so the run succeeds plainly, under a label the other side mustn't see.
  const id = await finishedRun(page, "slice-private");
  const other = await signedInPage(users.ownerB);
  const refused = await other.request.get(`/api/v1/runs/${id}/inspector`);
  expect(refused.status()).toBe(404);
  const refusedBody = await refused.text();
  expect(refusedBody).not.toContain("slice-private");
  await other.goto(`/runs/${id}/inspector`);
  await expect(other.locator('[data-state="unavailable"]')).toBeVisible();
  await expect(other.locator("main")).not.toContainText("slice-private");
  await other.goto("/runs");
  await expect(other.locator(`[data-run="${id}"]`)).toHaveCount(0);
});

// R-28: the inspector says why it can't read a run, as the run page does, and only an outage offers
// Retry. The replies are arranged with page.route on the inspector read.
test("the inspector says why it can't read a run, and Retry reads it again", async ({
  page,
}) => {
  const keyless = noKeyRun();
  await signIn(page, users.noKey);
  const inspector = (url: URL) =>
    url.pathname === `/api/v1/runs/${keyless}/inspector`;
  let arranged: Parameters<Route["fulfill"]>[0] | null = null;
  await page.route(inspector, (route) =>
    arranged === null ? route.continue() : route.fulfill(arranged),
  );
  const state = page.locator('[data-state="unavailable"]');
  for (const [reply, reason, words] of [
    [
      {
        status: 403,
        json: { code: "workspace_required", message: "Choose a workspace." },
      },
      "denied",
      "Choose a workspace.",
    ],
    [
      { status: 401, json: { code: "not_signed_in", message: "Arranged." } },
      "signed_out",
      "You're signed out. Sign in to see this run.",
    ],
    [
      { status: 422, json: { code: "validation_error", message: "Arranged." } },
      "not_found",
      "That run is not available. Sign in with access to it, or check the link.",
    ],
    [
      { status: 200, json: { schema_version: 1, model_calls: "arranged" } },
      "out_of_date",
      "This page and the local service disagree. Reload after updating.",
    ],
  ] as const) {
    arranged = reply;
    await page.goto(`/runs/${keyless}/inspector`);
    await expect(state).toHaveAttribute("data-reason", reason);
    await expect(state.getByRole("alert")).toHaveText(words);
    await expect(state.getByRole("button", { name: "Retry" })).toHaveCount(0);
  }
  arranged = {
    status: 503,
    json: {
      code: "service_unavailable",
      message: "The local API is unavailable.",
    },
  };
  await page.goto(`/runs/${keyless}/inspector`);
  await expect(state).toHaveAttribute("data-reason", "unavailable");
  await expect(state.getByRole("alert")).toHaveText(
    "This run can't be read right now. Check that the local services are running, then try again.",
  );
  arranged = null;
  await state.getByRole("button", { name: "Retry" }).click();
  await expect(state).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "Model calls" }),
  ).toBeVisible();
  await page.unroute(inspector);
});
