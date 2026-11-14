import { expect, test, type Page } from "@playwright/test";

// A run's controls, with the scripted worker running. Its name puts it with the slice suites.
const EMAIL_A = process.env.AUTOBOTS_TEST_OWNER_EMAIL ?? "";
const PASSWORD_A = process.env.AUTOBOTS_TEST_OWNER_PASSWORD ?? "";
const EMAIL_C = process.env.AUTOBOTS_TEST_MEMBER_EMAIL ?? "";
const PASSWORD_C = process.env.AUTOBOTS_TEST_MEMBER_PASSWORD ?? "";
const WORKSPACE_A = process.env.AUTOBOTS_TEST_WORKSPACE_A ?? "";

async function signIn(
  page: Page,
  email: string = EMAIL_A,
  password: string = PASSWORD_A,
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
      .fill("sk-or-valid-arranged-first");
    await page.getByRole("button", { name: "Save & validate" }).click();
    await expect(page.locator('[data-field="auth"]')).toHaveText(
      "The key authenticated.",
    );
  }
}

async function admit(page: Page, goal: string): Promise<string> {
  await page.goto("/");
  const reply = await page.request.post("/api/v1/runs", {
    headers: await write(page, `${goal}-${Date.now()}`),
    data: {
      goal_text: `${goal}: report the total of the two counts`,
      limit_micro_usd: 1000000,
      acceptance_criteria: ["The report states the correct total"],
      required_artifacts: [{ name: "report.md", must_contain: ["Total: 5"] }],
      input_documents: [
        { path: "inputs/data.md", content: "apples: 2\npears: 3\n" },
      ],
    },
  });
  expect(reply.status()).toBe(202);
  return (await reply.json()).run_id;
}

const status = (page: Page) => page.locator("[data-run-status]");
const button = (page: Page, name: string) =>
  page.getByRole("button", { name, exact: true });

async function apiStatus(page: Page, id: string): Promise<string> {
  return (await (await page.request.get(`/api/v1/runs/${id}`)).json()).status;
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
  await signIn(page);
  await ensureKey(page);
  const id = await admit(page, "slice-slow");
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

test("a finished run offers no control, whichever way it ended", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await signIn(page);
  await ensureKey(page);
  const succeeded = await admit(page, "slice-finishes");
  const failed = await admit(page, "slice-only-claims");
  const expected = { [succeeded]: "succeeded", [failed]: "failed" };
  for (const [id, state] of Object.entries(expected)) {
    await page.goto(`/runs/${id}`);
    await expect(status(page)).toHaveAttribute("data-run-status", state, {
      timeout: 40_000,
    });
    await expectNoControls(page);
    await expect(page.locator("[data-run-controls]")).toHaveCount(0);
    const reopened = await page.request.post(`/api/v1/runs/${id}/resume`, {
      headers: await write(page, `reopen-${id}`),
      data: {
        expected_version: (
          await (await page.request.get(`/api/v1/runs/${id}`)).json()
        ).version,
      },
    });
    expect(reopened.status()).toBe(409);
  }
});

test("resume is refused with its reason until an uncertain call is reconciled, and then accepted", async ({
  page,
  browser,
}) => {
  test.setTimeout(160_000);
  await signIn(page);
  await ensureKey(page);
  const id = await admit(page, "slice-uncertain");
  await page.goto(`/runs/${id}`);
  // The scripted worker dies inside a model call, and recovery stops at the unknown.
  await expect(status(page)).toHaveAttribute("data-run-status", "paused", {
    timeout: 60_000,
  });
  await expect(page.locator("[data-stop-reason]")).toContainText(
    "uncertain model call",
  );

  const before = await (
    await page.request.get(`/api/v1/runs/${id}/workspace`)
  ).json();
  expect(before.outstanding.uncertain_calls).toBe(1);

  await button(page, "Resume").click();
  await expect(page.locator("[data-control-refusal]")).toContainText(
    "A model call's outcome must be reconciled first.",
  );
  await page.waitForTimeout(3000);
  await expectState(page, id, "paused", "Paused.");
  const refused = await (
    await page.request.get(`/api/v1/runs/${id}/workspace`)
  ).json();
  expect(refused.usage.model_calls).toBe(before.usage.model_calls);

  // Someone who isn't the owner is refused, by the route and on the screen.
  const memberContext = await browser.newContext();
  const member = await memberContext.newPage();
  await signIn(member, EMAIL_C, PASSWORD_C);
  const denied = await member.request.post(
    `/api/v1/runs/${id}/model-calls/reconcile`,
    {
      headers: {
        ...(await write(member, "member-reconcile")),
        "X-Autobots-Workspace": WORKSPACE_A,
      },
      data: { charged_micro_usd: 1 },
    },
  );
  expect(denied.status()).toBe(403);
  expect((await denied.json()).code).toBe("owner_required");
  await memberContext.close();

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
  const after = await (
    await page.request.get(`/api/v1/runs/${id}/workspace`)
  ).json();
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
  const stale = await page.request.post(
    `/api/v1/runs/${id}/model-calls/reconcile`,
    {
      headers: await write(page, `stale-${id}`),
      data: { charged_micro_usd: 5 },
    },
  );
  expect((await stale.json()).reconciled_calls).toBe(0);
});
