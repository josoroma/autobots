import {
  parseReconciliationResult,
  parseRunWorkspace,
} from "@autobots/api-client";
import type { Page } from "@playwright/test";

import { expectRefusal, getJson, send, writeHeaders } from "./support/api.ts";
import { signIn, users } from "./support/auth.ts";
import { twoCountsRun, WorkerScenario } from "./support/builders.ts";
import { need } from "./support/env.ts";
import { expect, test } from "./support/fixtures.ts";
import { ensureProviderKey } from "./support/keys.ts";
import { admitRun, readRun, runCommand } from "./support/runs.ts";

// A run's controls, with the scripted worker running. Its name puts it with the slice suites.

/** Admits the two-counts run for `scenario` from Home. */
async function admit(page: Page, scenario: string): Promise<string> {
  await page.goto("/");
  return admitRun(page, twoCountsRun(scenario), {
    key: `${scenario}-${Date.now()}`,
  });
}

function workspace(page: Page, id: string) {
  return getJson(page, {
    path: `/api/v1/runs/${id}/workspace`,
    parse: parseRunWorkspace,
  });
}

const status = (page: Page) => page.locator("[data-run-status]");
const button = (page: Page, name: string) =>
  page.getByRole("button", { name, exact: true });

async function apiStatus(page: Page, id: string): Promise<string> {
  return (await readRun(page, id)).status;
}

// The page's text state, and the one the API reports, agree.
async function expectState(
  page: Page,
  id: string,
  state: string,
  text: string,
): Promise<void> {
  await expect(status(page)).toHaveAttribute("data-run-status", state, {
    timeout: 40_000,
  });
  await expect(status(page)).toContainText(text);
  expect(await apiStatus(page, id)).toBe(state);
}

async function expectNoControls(page: Page): Promise<void> {
  for (const name of ["Pause", "Resume", "Cancel run"]) {
    await expect(button(page, name)).toHaveCount(0);
  }
}

test("a person pauses, resumes and cancels a running run from its page, and the page matches the API", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await signIn(page, users.owner);
  await ensureProviderKey(page);
  const id = await admit(page, WorkerScenario.slow);
  await page.goto(`/runs/${id}`);
  await expectState(page, id, "running", "Running.");

  await button(page, "Pause").click();
  await expectState(page, id, "paused", "Paused.");
  await expect(button(page, "Pause")).toHaveCount(0);

  await button(page, "Resume").click();
  await expect(status(page)).not.toHaveAttribute("data-run-status", "paused", {
    timeout: 20_000,
  });
  await expectState(page, id, "running", "Running.");

  await button(page, "Cancel run").click();
  await expectState(page, id, "cancelled", "Cancelled.");
  await expectNoControls(page);
  await page.reload();
  await expectState(page, id, "cancelled", "Cancelled.");
  await expectNoControls(page);
});

test("after a lost Pause, Resume sends nothing, and Cancel still stops the run", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await signIn(page, users.owner);
  await ensureProviderKey(page);
  const id = await admit(page, WorkerScenario.slow);
  await page.goto(`/runs/${id}`);
  await expectState(page, id, "running", "Running.");
  // Decision 0027 D2: the Pause reaches the API and applies, but its reply is lost. Pause and Resume
  // share the run as their target, so Resume can't send until a reload shows what the Pause did.
  // Cancel has its own target, so the lost Pause never holds back stopping the run.
  const pauses = `**/api/v1/runs/${id}/pause`;
  const resumes = `**/api/v1/runs/${id}/resume`;
  const cancels = `**/api/v1/runs/${id}/cancel`;
  const paused: string[] = [];
  const resumed: string[] = [];
  const cancelled: string[] = [];
  await page.route(pauses, async (route) => {
    paused.push(route.request().headers()["idempotency-key"] ?? "");
    await route.fetch();
    return route.abort("connectionreset");
  });
  await page.route(resumes, (route) => {
    resumed.push(route.request().headers()["idempotency-key"] ?? "");
    return route.continue();
  });
  await page.route(cancels, (route) => {
    cancelled.push(route.request().headers()["idempotency-key"] ?? "");
    return route.continue();
  });
  await button(page, "Pause").click();
  await expectState(page, id, "paused", "Paused.");
  await button(page, "Resume").click();
  await expect(
    page.getByText(/Nothing was sent\. Your first choice, "Pause"/),
  ).toBeVisible();
  expect(resumed).toHaveLength(0);
  expect(paused).toHaveLength(1);
  await button(page, "Cancel run").click();
  await expectState(page, id, "cancelled", "Cancelled.");
  expect(cancelled).toHaveLength(1);
  await page.unroute(pauses);
  await page.unroute(resumes);
  await page.unroute(cancels);
  await page.reload();
  await expectState(page, id, "cancelled", "Cancelled.");
  await expectNoControls(page);
});

test("a finished run offers no control, whichever way it ended", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await signIn(page, users.owner);
  await ensureProviderKey(page);
  // A goal with no scenario word runs plainly to success.
  const succeeded = await admit(page, "slice-finishes");
  const failed = await admit(page, WorkerScenario.onlyClaims);
  const expected = { [succeeded]: "succeeded", [failed]: "failed" };
  for (const [id, state] of Object.entries(expected)) {
    await page.goto(`/runs/${id}`);
    await expect(status(page)).toHaveAttribute("data-run-status", state, {
      timeout: 40_000,
    });
    await expectNoControls(page);
    await expect(page.locator("[data-run-controls]")).toHaveCount(0);
    const reopened = await runCommand(page, {
      run: id,
      command: "resume",
      expectedVersion: (await readRun(page, id)).version,
      key: `reopen-${id}`,
    });
    expect(reopened.status()).toBe(409);
  }
});

test("resume is refused with its reason until an uncertain call is reconciled, and then accepted", async ({
  page,
  signedInPage,
}) => {
  test.setTimeout(160_000);
  await signIn(page, users.owner);
  await ensureProviderKey(page);
  const id = await admit(page, WorkerScenario.uncertain);
  await page.goto(`/runs/${id}`);
  // The scripted worker dies inside a model call, and recovery stops at the unknown.
  await expect(status(page)).toHaveAttribute("data-run-status", "paused", {
    timeout: 60_000,
  });
  await expect(page.locator("[data-stop-reason]")).toContainText(
    "uncertain model call",
  );

  const before = await workspace(page, id);
  expect(before.outstanding.uncertain_calls).toBe(1);

  await button(page, "Resume").click();
  await expect(page.locator("[data-control-refusal]")).toContainText(
    "A model call's outcome must be reconciled first.",
  );
  await page.waitForTimeout(3000);
  await expectState(page, id, "paused", "Paused.");
  const refused = await workspace(page, id);
  expect(refused.usage.model_calls).toBe(before.usage.model_calls);

  // Someone who isn't the owner is refused, by the route and on the screen.
  const member = await signedInPage(users.member);
  const denied = await member.request.post(
    `/api/v1/runs/${id}/model-calls/reconcile`,
    {
      headers: {
        ...(await writeHeaders(member, "member-reconcile")),
        "X-Autobots-Workspace": need("AUTOBOTS_TEST_WORKSPACE_A"),
      },
      data: { charged_micro_usd: 1 },
    },
  );
  await expectRefusal(denied, { status: 403, code: "owner_required" });

  await page.route("**/model-calls/reconcile", (route) =>
    route.fulfill({
      status: 403,
      contentType: "application/json",
      body: JSON.stringify({
        code: "owner_required",
        message: "Only the workspace owner can change this.",
      }),
    }),
  );
  await page.getByLabel("Charge seen, in US dollars").fill("0.00025");
  await page.getByRole("button", { name: "Record the charge" }).click();
  await expect(page.locator("[data-control-refusal]")).toContainText(
    "Only the workspace owner",
  );
  await page.unroute("**/model-calls/reconcile");

  await page.getByLabel("Charge seen, in US dollars").fill("not a number");
  await page.getByRole("button", { name: "Record the charge" }).click();
  await expect(page.locator("[data-control-refusal]")).toContainText(
    "Enter the charge in US dollars",
  );

  // R-18 step 1, Decision 0027 D2: the charge reaches the API and its reply is lost, so the page
  // can't tell it was recorded. The run's own reloads are lost too, so the form stays, and the
  // next press resends the same request under the same key, which records it once.
  const charged: { key: string; body: string | null }[] = [];
  const snapshot = `**/api/v1/runs/${id}/workspace`;
  await page.route(snapshot, (route) => route.abort("connectionreset"));
  await page.route("**/model-calls/reconcile", async (route) => {
    charged.push({
      key: route.request().headers()["idempotency-key"] ?? "",
      body: route.request().postData(),
    });
    if (charged.length > 1) return route.continue();
    await route.fetch();
    return route.abort("connectionreset");
  });
  const charge = page.getByLabel("Charge seen, in US dollars");
  await charge.fill("0.00025");
  await page.getByRole("button", { name: "Record the charge" }).click();
  await expect(page.locator("[data-control-refusal]")).toContainText(
    "This may have been recorded",
  );
  await expect(charge).not.toBeEditable();
  await expect(charge).toHaveValue("0.00025");
  await page.getByRole("button", { name: "Record the charge" }).click();
  await expect(page.locator("[data-control-note]")).toContainText(
    "The charge is recorded",
  );
  expect(charged).toHaveLength(2);
  expect(charged[1]).toEqual(charged[0]);
  await page.unroute("**/model-calls/reconcile");
  await page.unroute(snapshot);
  await page.reload();
  await expect(page.locator("[data-reconcile]")).toHaveCount(0);
  const after = await workspace(page, id);
  expect(after.outstanding.uncertain_calls).toBe(0);
  expect(
    after.run.budget.spent_micro_usd - before.run.budget.spent_micro_usd,
  ).toBe(250);

  await button(page, "Resume").click();
  await expect(status(page)).toHaveAttribute("data-run-status", "succeeded", {
    timeout: 60_000,
  });
  expect(await apiStatus(page, id)).toBe("succeeded");
  await expectNoControls(page);

  // E-2: the audit screen doesn't call that call a success, or the owner's figure a report.
  await page.goto(`/runs/${id}/inspector`);
  const entered = page.locator('[data-cost="entered"]');
  await expect(entered).toContainText("Charge entered by the owner");
  await expect(entered).toContainText("US$0.00025");
  await expect(
    page.locator("[data-call]").filter({ has: entered }),
  ).toContainText("outcome unknown");

  // E-6: a stale tab is told nothing was recorded.
  await page.goto(`/runs/${id}`);
  const stale = await send(page, {
    path: `/api/v1/runs/${id}/model-calls/reconcile`,
    key: `stale-${id}`,
    data: { charged_micro_usd: 5 },
    status: 200,
    parse: parseReconciliationResult,
  });
  expect(stale.reconciled_calls).toBe(0);
});
