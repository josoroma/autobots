import {
  parseReconciliationResult,
  parseRunAccepted,
  parseRunCommandResult,
} from "@autobots/api-client";
import type { Page, Route } from "@playwright/test";

import { expectNoA11yViolations } from "./support/a11y.ts";
import { expectRefusal, send, writeHeaders } from "./support/api.ts";
import { signIn, users } from "./support/auth.ts";
import { expect, test } from "./support/fixtures.ts";
import { disconnectProviderKey, ensureProviderKey } from "./support/keys.ts";
import { admitRun, readRun, runCommand } from "./support/runs.ts";

// Admission needs a usable key. The last test here removes it, and the settings spec expects none.
async function signInWithKey(page: Page): Promise<void> {
  await signIn(page, users.owner);
  await ensureProviderKey(page);
  await page.goto("/");
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
  await page.getByRole("button", { name: "Run", exact: true }).click();
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
  const admit = () =>
    send(page, {
      path: "/api/v1/runs",
      key: "api-key-1",
      data,
      status: 202,
      parse: parseRunAccepted,
    });
  const accepted = await admit();
  expect(accepted.status).toBe("queued");
  expect(accepted.replayed).toBe(false);
  expect((await admit()).run_id).toBe(accepted.run_id);
  const conflict = await page.request.post("/api/v1/runs", {
    headers: await writeHeaders(page, "api-key-1"),
    data: { ...data, goal_text: "Different" },
  });
  await expectRefusal(conflict, { status: 409, code: "idempotency_conflict" });
  const missing = await page.request.post("/api/v1/runs", {
    headers: { ...(await writeHeaders(page, "x")), "Idempotency-Key": "" },
    data,
  });
  expect(missing.status()).toBe(422);
});

test("commands follow the table through the API, and terminal runs stay closed", async ({
  page,
}) => {
  await signInWithKey(page);
  const id = await admitRun(
    page,
    { goal_text: "Commands", limit_micro_usd: 1000 },
    { key: "api-key-2" },
  );
  const command = (
    name: "pause" | "resume" | "cancel",
    expectedVersion: number,
    key: string,
  ) => runCommand(page, { run: id, command: name, expectedVersion, key });
  const result = async (
    name: "pause" | "resume" | "cancel",
    version: number,
    key: string,
  ) => {
    const reply = await command(name, version, key);
    expect(reply.status(), `${name} ${await reply.text()}`).toBe(200);
    return parseRunCommandResult(await reply.json());
  };
  expect((await result("pause", 1, "c1")).status).toBe("paused");
  await expectRefusal(await command("resume", 1, "c2"), {
    status: 409,
    code: "version_conflict",
  });
  expect((await result("resume", 2, "c3")).status).toBe("queued");
  const invalid = await page.request.post(`/api/v1/runs/${id}/input`, {
    headers: await writeHeaders(page, "c4"),
    data: { expected_version: 3, value: "an answer" },
  });
  await expectRefusal(invalid, { status: 409, code: "transition_refused" });
  expect((await result("cancel", 3, "c5")).status).toBe("cancelled");
  const reopened = await command("resume", 4, "c6");
  expect(reopened.status()).toBe(409);
  const summary = await readRun(page, id);
  expect(summary.status).toBe("cancelled");
  expect(summary.version).toBe(4);
  expect(JSON.stringify(summary)).not.toContain("lease");
  expect(JSON.stringify(summary)).not.toContain("policy_snapshot");
});

test("another workspace cannot see or command the run", async ({
  openPage,
  signedInPage,
}) => {
  const owner = await openPage();
  await signInWithKey(owner);
  const id = await admitRun(
    owner,
    { goal_text: "Private", limit_micro_usd: 1000 },
    { key: "api-key-3" },
  );
  const other = await signedInPage(users.ownerB);
  expect((await other.request.get(`/api/v1/runs/${id}`)).status()).toBe(404);
  const pause = await runCommand(other, {
    run: id,
    command: "pause",
    expectedVersion: 1,
    key: "foreign",
  });
  expect(pause.status()).toBe(404);
});

test("resume checks readiness, and a finished run takes a linked new run", async ({
  page,
}) => {
  await signInWithKey(page);
  const id = await admitRun(
    page,
    { goal_text: "Readiness", limit_micro_usd: 1000 },
    { key: "api-key-5" },
  );
  const pause = await runCommand(page, {
    run: id,
    command: "pause",
    expectedVersion: 1,
    key: "r1",
  });
  expect(parseRunCommandResult(await pause.json()).status).toBe("paused");
  await disconnectProviderKey(page);
  const refused = await runCommand(page, {
    run: id,
    command: "resume",
    expectedVersion: 2,
    key: "r2",
  });
  await expectRefusal(refused, { status: 409, code: "credentials_required" });
  await signInWithKey(page);
  const resumed = await runCommand(page, {
    run: id,
    command: "resume",
    expectedVersion: 2,
    key: "r3",
  });
  expect(parseRunCommandResult(await resumed.json()).status).toBe("queued");
  const early = await page.request.post("/api/v1/runs", {
    headers: await writeHeaders(page, "api-key-6"),
    data: {
      goal_text: "Too early",
      limit_micro_usd: 1000,
      continues_run_id: id,
    },
  });
  await expectRefusal(early, { status: 409, code: "run_not_continuable" });
  await runCommand(page, {
    run: id,
    command: "cancel",
    expectedVersion: 3,
    key: "r4",
  });
  const linked = await page.request.post("/api/v1/runs", {
    headers: await writeHeaders(page, "api-key-7"),
    data: {
      goal_text: "Continue",
      limit_micro_usd: 1000,
      continues_run_id: id,
    },
  });
  expect(linked.status()).toBe(202);
  const reconcile = await send(page, {
    path: `/api/v1/runs/${id}/model-calls/reconcile`,
    key: "r5",
    data: { charged_micro_usd: 5 },
    status: 200,
    parse: parseReconciliationResult,
  });
  expect(reconcile.reconciled_calls).toBe(0);
});

test("a workspace with no key cannot admit a run", async ({ page }) => {
  await signInWithKey(page);
  await disconnectProviderKey(page);
  const refused = await page.request.post("/api/v1/runs", {
    headers: await writeHeaders(page, "no-key"),
    data: { goal_text: "Blocked", limit_micro_usd: 1000 },
  });
  await expectRefusal(refused, { status: 409, code: "credentials_required" });
});

// US-15.4: an arranged workspace with 101 runs and three with known spend (scripts/qualify_identity.py).
const HELD = "44444444-4444-4444-8444-000000000001";
const UNREPORTED = "44444444-4444-4444-8444-000000000002";
const REPORTED = "44444444-4444-4444-8444-000000000003";

test("status tabs, filters, paging and estimated spend on Runs", async ({
  page,
}) => {
  await signIn(page, users.runs);
  await page.goto("/runs");
  const tab = (id: string) => page.locator(`[data-group="${id}"]`);
  await expect(tab("all")).toHaveText("All 101");
  await expect(tab("active")).toHaveText("Active 50");
  await expect(tab("needs_you")).toHaveText("Needs you 24");
  await expect(tab("finished")).toHaveText("Finished 27");
  await expect(tab("all")).toHaveAttribute("aria-pressed", "true");

  const rows = page.locator("[data-run]");
  await expect(rows).toHaveCount(100);
  await expect(page.locator('[data-state="shown"]')).toHaveText(
    "Showing 100 of 101",
  );
  await page.getByRole("button", { name: "Load more" }).click();
  await expect(rows).toHaveCount(101);
  const ids = await rows.evaluateAll((items) =>
    items.map((item) => item.getAttribute("data-run")),
  );
  expect(new Set(ids).size).toBe(101);
  await expect(page.getByRole("button", { name: "Load more" })).toHaveCount(0);

  const spend = (id: string) =>
    page.locator(`[data-run="${id}"] [data-field="spend"]`);
  await expect(spend(HELD)).toContainText("≈");
  await expect(spend(HELD)).toContainText("US$0.18");
  await expect(spend(HELD)).toContainText("estimated, of US$1.00");
  await expect(spend(UNREPORTED)).toContainText("≈");
  await expect(spend(UNREPORTED)).toContainText("estimated");
  await expect(spend(REPORTED)).not.toContainText("≈");
  await expect(spend(REPORTED)).not.toContainText("estimated");
  await expect(spend(REPORTED)).toContainText("US$0.07");
  await expect(spend(REPORTED)).toContainText("of US$1.00");

  await expectNoA11yViolations(page);

  await tab("needs_you").click();
  await expect(tab("needs_you")).toHaveAttribute("aria-pressed", "true");
  await expect(rows).toHaveCount(24);
  for (const status of await rows.evaluateAll((items) =>
    items.map((item) => item.getAttribute("data-status")),
  ))
    expect(status).toBe("waiting_input");
  await expect(page.locator('[data-state="shown"]')).toHaveText(
    "Showing 24 of 24",
  );

  await tab("all").click();
  const searched = page.waitForResponse((reply) =>
    reply.url().includes("q=fully+reported"),
  );
  await page
    .getByPlaceholder("Filter by goal or Expert")
    .fill("fully reported");
  await searched;
  await expect(rows).toHaveCount(1);
  await expect(rows.first()).toHaveAttribute("data-run", REPORTED);
  await expect(tab("all")).toHaveText("All 1");

  await page.getByPlaceholder("Filter by goal or Expert").fill("");
  // Wait for the filtered page itself, so a row left from the text filter can't satisfy the count.
  const filtered = page.waitForResponse(
    (reply) =>
      reply.url().includes("profile=openrouter_sol") &&
      !reply.url().includes("q="),
  );
  await page.getByLabel("Model").selectOption("openrouter_sol");
  await filtered;
  await expect(rows).toHaveCount(1);
  await expect(rows.first()).toHaveAttribute("data-run", HELD);
  await expect(
    page.locator(`[data-run="${HELD}"] [data-field="models"]`),
  ).toContainText("Sol");
});

// R-27: each way the list can fail reads differently, and only an outage offers Retry. The replies
// are arranged with page.route on the list's first page, plain /api/v1/runs.
test("the run list says why it can't be read, and Retry reads it again", async ({
  page,
}) => {
  await signIn(page, users.owner);
  let arranged: Parameters<Route["fulfill"]>[0] | null = null;
  await page.route("**/api/v1/runs", (route) =>
    arranged === null || route.request().method() !== "GET"
      ? route.continue()
      : route.fulfill(arranged),
  );
  const state = page.locator('[data-state="unavailable"]');
  for (const [reply, reason, words] of [
    [
      {
        status: 403,
        json: { code: "not_a_member", message: "Members only, arranged." },
      },
      "denied",
      "Members only, arranged.",
    ],
    [
      {
        status: 422,
        json: { code: "validation_failed", message: "Arranged." },
      },
      "not_found",
      "Runs can't be found.",
    ],
    [
      { status: 200, json: { schema_version: 1, runs: "arranged" } },
      "out_of_date",
      "This page and the local service disagree. Reload after updating.",
    ],
  ] as const) {
    arranged = reply;
    await page.goto("/runs");
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
  await page.goto("/runs");
  await expect(state).toHaveAttribute("data-reason", "unavailable");
  await expect(state.getByRole("alert")).toHaveText(
    "Runs can't be read right now. Check that the local services are running, then try again.",
  );
  arranged = null;
  await state.getByRole("button", { name: "Retry" }).click();
  await expect(state).toHaveCount(0);
  await expect(
    page.locator('[data-state="shown"], [data-state="empty"]'),
  ).toBeVisible();
});
