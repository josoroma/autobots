import { execFileSync } from "node:child_process";

import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

const EMAIL_A = process.env.AUTOBOTS_TEST_OWNER_EMAIL ?? "";
const PASSWORD_A = process.env.AUTOBOTS_TEST_OWNER_PASSWORD ?? "";
const EMAIL_B = process.env.AUTOBOTS_TEST_OWNER_B_EMAIL ?? "";
const PASSWORD_B = process.env.AUTOBOTS_TEST_OWNER_B_PASSWORD ?? "";
const LOOP_RUN = process.env.AUTOBOTS_TEST_LOOP_RUN ?? "";
const GAP_RUN = process.env.AUTOBOTS_TEST_ARTIFACT_RUN ?? "";
// US-14.4, arranged by tests/db/tool_use_view_check.py.
const TOOL_RUN = process.env.AUTOBOTS_TEST_TOOL_RUN ?? "";
const TOOL_EXECUTION = process.env.AUTOBOTS_TEST_TOOL_EXECUTION ?? "";
const RUN_NOT_FOUND =
  "That run is not available. Sign in with access to it, or check the link.";
const OUTAGE = {
  status: 503,
  json: {
    code: "service_unavailable",
    message: "The local API is unavailable.",
  },
};

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

/** The paths under one run that the page itself asks for, in order. */
function runRequests(page: Page, runId: string): string[] {
  const asked: string[] = [];
  page.on("request", (request) => {
    const path = new URL(request.url()).pathname;
    if (path.startsWith(`/api/v1/runs/${runId}/`)) asked.push(path);
  });
  return asked;
}

/** Matches one run's snapshot read, for page.route. */
function snapshotOf(runId: string): (url: URL) => boolean {
  return (url) => url.pathname === `/api/v1/runs/${runId}/workspace`;
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

  const later = await (
    await page.request.get(`/api/v1/runs/${id}/events?after=3`)
  ).json();
  expect(
    later.events.map((event: { sequence: number }) => event.sequence),
  ).toEqual([4]);
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
  const asked = runRequests(page, LOOP_RUN);
  await page.goto(`/runs/${LOOP_RUN}`);
  const state = page.locator('[data-state="unavailable"]');
  await expect(state).toBeVisible();
  // R-28: a missing run says so once. Nothing reads it again, and no stream opens.
  await expect(state).toHaveAttribute("data-reason", "not_found");
  await expect(state.getByRole("alert")).toHaveText(RUN_NOT_FOUND);
  await expect(state.getByRole("button", { name: "Retry" })).toHaveCount(0);
  // Longer than the first two attempts would take, had it kept trying.
  await page.waitForTimeout(3_500);
  expect(asked).toEqual([`/api/v1/runs/${LOOP_RUN}/workspace`]);
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

// R-28: a refusal, a malformed id and a drifted reply each say so once and stop: no Retry, no
// further reads and no stream. The replies are arranged with page.route on the snapshot read.
test("a refusal, a malformed id and a drifted reply each stop the run page", async ({
  page,
}) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
  const asked = runRequests(page, LOOP_RUN);
  const logged: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") logged.push(message.text());
  });
  let arranged: Parameters<Route["fulfill"]>[0] = OUTAGE;
  await page.route(snapshotOf(LOOP_RUN), (route) => route.fulfill(arranged));
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
      { status: 422, json: { code: "validation_error", message: "Arranged." } },
      "not_found",
      RUN_NOT_FOUND,
    ],
    [
      { status: 200, json: { schema_version: 1, run: "arranged" } },
      "out_of_date",
      "This page and the local service disagree. Reload after updating.",
    ],
  ] as const) {
    arranged = reply;
    asked.length = 0;
    await page.goto(`/runs/${LOOP_RUN}`);
    await expect(state).toHaveAttribute("data-reason", reason);
    await expect(state.getByRole("alert")).toHaveText(words);
    await expect(state.getByRole("button", { name: "Retry" })).toHaveCount(0);
    await expect(page.locator('[data-field="retry-in"]')).toHaveCount(0);
    // Longer than the first two attempts would take, had it kept trying.
    await page.waitForTimeout(3_500);
    expect(asked).toEqual([`/api/v1/runs/${LOOP_RUN}/workspace`]);
  }
  expect(
    logged.some((line) =>
      line.includes("This page and the local service disagree."),
    ),
  ).toBe(true);
  await page.unroute(snapshotOf(LOOP_RUN));

  // The API's own reply to an id that isn't a UUID, unarranged.
  await page.goto("/runs/not-a-run");
  await expect(state).toHaveAttribute("data-reason", "not_found");
  await expect(state.getByRole("alert")).toHaveText(RUN_NOT_FOUND);
});

// R-28: an outage is tried again after 1, 2 and 4 seconds, saying when, and Retry reads at once.
test("an outage backs off with a visible Retry, and the run shows when it recovers", async ({
  page,
}) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
  const times: number[] = [];
  let failing = 2;
  await page.route(snapshotOf(LOOP_RUN), (route) => {
    times.push(Date.now());
    if (failing === 0) return route.continue();
    failing -= 1;
    return route.fulfill(OUTAGE);
  });
  await page.goto(`/runs/${LOOP_RUN}`);
  const state = page.locator('[data-state="unavailable"]');
  const note = page.locator('[data-field="retry-in"]');
  const status = page.locator("[data-run-status]");
  await expect(state).toHaveAttribute("data-reason", "unavailable");
  await expect(state.getByRole("alert")).toHaveText(
    "This run can't be read right now. Check that the local services are running, then try again.",
  );
  await expect(state.getByRole("button", { name: "Retry" })).toBeVisible();
  await expect(note).toHaveText("Trying again in 2 seconds.");
  await expect(note).toHaveAttribute("data-attempt", "2");
  // It recovers on its own once the read succeeds.
  await expect(status).toHaveAttribute("data-run-status", "failed", {
    timeout: 10_000,
  });
  await expect(note).toHaveCount(0);
  const [first = 0, second = 0, third = 0] = times;
  expect(second - first).toBeGreaterThanOrEqual(900);
  expect(third - second).toBeGreaterThanOrEqual(1_900);

  failing = Number.POSITIVE_INFINITY;
  await page.reload();
  await expect(note).toHaveText("Trying again in 4 seconds.", {
    timeout: 10_000,
  });
  await expect(note).toHaveAttribute("data-attempt", "3");
  failing = 0;
  // Sooner than the next attempt would come by itself.
  await state.getByRole("button", { name: "Retry" }).click();
  await expect(status).toHaveAttribute("data-run-status", "failed", {
    timeout: 2_000,
  });
  await expect(page.locator("[data-connection]")).toHaveAttribute(
    "data-connection",
    "ended",
    { timeout: 15_000 },
  );
  await page.unroute(snapshotOf(LOOP_RUN));
});

// R-28: snapshot reads run one at a time, and a reply older than the snapshot shown is discarded.
// The first read after the route is installed is held, then answered with a snapshot older than
// the page's (cursor 0, with a status this run never reaches), as a reply that lost a race would
// be. Later reads go through.
test("an older snapshot reply that arrives late never replaces a newer one", async ({
  page,
}) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
  const id = await admitted(page, "order");
  await page.goto(`/runs/${id}`);
  const status = page.locator("[data-run-status]");
  await expect(status).toHaveAttribute("data-run-status", "queued");
  await expect(page.locator("[data-connection]")).toHaveAttribute(
    "data-connection",
    "live",
  );
  // Every status the page shows from here on, including one replaced at once.
  await page.evaluate(() => {
    const shown = document.querySelector("[data-run-status]");
    if (shown === null) throw new Error("The run's status isn't shown.");
    const seen: string[] = [];
    new MutationObserver((records) => {
      for (const record of records) seen.push(record.oldValue ?? "");
      seen.push(shown.getAttribute("data-run-status") ?? "");
      document.body.dataset.seenStatuses = seen.join(" ");
    }).observe(shown, {
      attributeFilter: ["data-run-status"],
      attributeOldValue: true,
    });
  });
  let reads = 0;
  let served = false;
  await page.route(snapshotOf(id), async (route) => {
    reads += 1;
    if (reads > 1) return route.continue();
    const reply = await route.fetch();
    const body = await reply.json();
    await new Promise((resolve) => setTimeout(resolve, 1_500));
    await route.fulfill({
      response: reply,
      json: { ...body, cursor: 0, run: { ...body.run, status: "succeeded" } },
    });
    served = true;
  });
  expect((await command(page, id, "pause", 1, "o1")).status()).toBe(200);
  expect((await command(page, id, "resume", 2, "o2")).status()).toBe(200);
  await expect.poll(() => served, { timeout: 10_000 }).toBe(true);
  // The read queued behind the held one starts only once the page has dealt with its reply.
  await expect.poll(() => reads, { timeout: 10_000 }).toBeGreaterThanOrEqual(2);
  await expect(page.locator('[data-sequence="3"]')).toContainText(
    "paused to queued",
  );
  // Time for the held reply to reach the screen, had it been applied.
  await page.waitForTimeout(500);
  await expect(status).toHaveAttribute("data-run-status", "queued");
  const seen =
    (await page.locator("body").getAttribute("data-seen-statuses")) ?? "";
  expect(seen.split(" ")).not.toContain("succeeded");
  await page.unroute(snapshotOf(id));
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
  await page.getByRole("button", { name: "Run", exact: true }).click();
  await page.getByRole("link", { name: "Open this run" }).click();
  await expect(page).toHaveURL(/\/runs\//);
  await expect(
    page.getByRole("region", { name: "Goal" }).getByRole("paragraph"),
  ).toHaveText("Open what I started");
  // The settings spec, which runs after this one, expects no key.
  await disconnectKey(page);
});

async function noViolations(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(results.violations.map((violation) => violation.id)).toEqual([]);
}

test("US-14.4: tool uses show live, once each and in order, and again after a reload", async ({
  page,
}) => {
  expect(TOOL_RUN).not.toBe("");
  await signIn(page, EMAIL_A, PASSWORD_A);
  await page.goto(`/runs/${TOOL_RUN}`);
  const section = page.getByRole("region", { name: "Tools used" });
  const rows = section.locator("[data-tool-use]");
  await expect(rows).toHaveCount(2);
  await expect(rows.nth(0)).toHaveAttribute("data-tool-id", "calculate");
  await expect(rows.nth(0).locator('[data-field="task"]')).toHaveText(
    "Add the totals",
  );
  await expect(rows.nth(0).locator('[data-field="inputs"]')).toHaveText(
    "operation: sum",
  );
  await expect(rows.nth(0).locator('[data-field="result"]')).toHaveText(
    "result: 3",
  );
  await expect(rows.nth(0).locator('[data-field="outcome"]')).toHaveText(
    "Succeeded",
  );
  await expect(rows.nth(1)).toHaveAttribute("data-tool-id", "publish_artifact");
  await expect(rows.nth(1).locator('[data-field="task"]')).toHaveText(
    "No plan task",
  );
  await expect(rows.nth(1).locator('[data-field="outcome"]')).toHaveText(
    "Denied: tool not granted",
  );
  await expect(page.locator("[data-connection]")).toHaveAttribute(
    "data-connection",
    "live",
    { timeout: 15_000 },
  );

  // A worker's call while the page watches, through the same gateway.
  const made = execFileSync(
    process.env.AUTOBOTS_TEST_PYTHON ?? "",
    [
      process.env.AUTOBOTS_TEST_TOOL_HELPER ?? "",
      TOOL_RUN,
      process.env.AUTOBOTS_TEST_TOOL_GENERATION ?? "",
      process.env.AUTOBOTS_TEST_TOOL_WORKSPACE ?? "",
    ],
    {
      env: {
        ...process.env,
        AUTOBOTS_DATABASE_URL: process.env.AUTOBOTS_TEST_RUNTIME_URL ?? "",
        PYTHONPATH: process.env.AUTOBOTS_TEST_PYTHONPATH ?? "",
      },
      encoding: "utf8",
    },
  );
  expect(JSON.parse(made.trim().split("\n").at(-1) ?? "{}").outcome).toBe(
    "succeeded",
  );
  await expect(rows).toHaveCount(3, { timeout: 15_000 });
  const third = rows.nth(2);
  await expect(third).toHaveAttribute("data-tool-id", "save_artifact");
  await expect(third.locator('[data-field="task"]')).toHaveText(
    "Save the note",
  );
  await expect(third.locator('[data-field="inputs"]')).toHaveText(
    "path: outputs/live.md; media_type: text/markdown",
  );
  await expect(third.locator('[data-field="outcome"]')).toHaveText("Succeeded");
  await expect(page.locator('[data-field="tool-announcement"]')).toHaveText(
    "save_artifact: Succeeded. 3 tool uses.",
  );
  await expect(
    page.locator('[data-field="tool-announcement"]'),
  ).toHaveAttribute("aria-live", "polite");
  expect(await page.content()).not.toContain("written live");
  await noViolations(page);

  await page.reload();
  await expect(rows).toHaveCount(3);
  const ids = await rows.evaluateAll((items) =>
    items.map((item) => Number(item.getAttribute("data-tool-use"))),
  );
  expect(ids).toEqual([...ids].sort((a, b) => a - b));
  expect(new Set(ids).size).toBe(3);
  await expect(
    section.getByRole("columnheader", { name: "Plan task" }),
  ).toBeVisible();
});

test("US-14.4: the workflow monitor shows tool uses under the node that made them", async ({
  page,
}) => {
  expect(TOOL_EXECUTION).not.toBe("");
  await signIn(page, EMAIL_A, PASSWORD_A);
  await page.goto(`/workflow-executions/${TOOL_EXECUTION}`);
  const read = page.locator('[data-node-tools="read"]');
  await expect(read.getByRole("heading", { name: "Node read" })).toBeVisible();
  await expect(read.locator('[data-tool-id="read_run_file"]')).toHaveCount(1);
  await expect(read.locator("[data-tool-use]")).toHaveCount(1);
  const save = page.locator('[data-node-tools="save"]');
  await expect(save.locator('[data-tool-id="save_artifact"]')).toHaveCount(1);
  await expect(save.locator('[data-tool-id="read_run_file"]')).toHaveCount(0);
  await expect(page.locator('[data-node-tools="in"]')).toHaveCount(0);
  await noViolations(page);

  // R-27: tool uses that can't be read say so, and Retry reads them again.
  const toolUses = (url: URL) => url.pathname.endsWith("/tool-uses");
  await page.route(toolUses, (route) =>
    route.fulfill({
      status: 503,
      json: {
        code: "service_unavailable",
        message: "The local API is unavailable.",
      },
    }),
  );
  await page.reload();
  const failure = page
    .getByRole("region", { name: "Tool uses by node" })
    .locator('[data-state="unavailable"]');
  await expect(failure).toHaveAttribute("data-reason", "unavailable");
  await expect(failure.getByRole("alert")).toHaveText(
    "Tool uses can't be read right now. Check that the local services are running, then try again.",
  );
  await page.unroute(toolUses);
  await failure.getByRole("button", { name: "Retry" }).click();
  await expect(read.locator("[data-tool-use]")).toHaveCount(1);
});

function probe(
  runId: string,
): { path: string; media_type: string; bytes: number }[] {
  const script = (process.env.AUTOBOTS_TEST_TOOL_HELPER ?? "").replace(
    "tool_use_live.py",
    "run_files_probe.py",
  );
  const printed = execFileSync(
    process.env.AUTOBOTS_TEST_PYTHON ?? "",
    [script, runId],
    {
      env: {
        ...process.env,
        AUTOBOTS_DATABASE_URL: process.env.AUTOBOTS_TEST_RUNTIME_URL ?? "",
        PYTHONPATH: process.env.AUTOBOTS_TEST_PYTHONPATH ?? "",
      },
      encoding: "utf8",
    },
  );
  return JSON.parse(printed.trim().split("\n").at(-1) ?? "[]");
}

test("US-14.9: up to five text files attach to a goal as run inputs, and the rest are refused", async ({
  page,
}) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
  await admitted(page, `attach-${Date.now()}`);
  await page.goto("/");
  const input = page.getByLabel("Attach files");
  const text = (name: string, mimeType: string, body: string) => ({
    name,
    mimeType,
    buffer: Buffer.from(body),
  });
  await input.setInputFiles([
    text("notes.txt", "text/plain", "plain notes"),
    text("plan.md", "text/markdown", "# Plan"),
    text("data.json", "application/json", '{"a": 1}'),
    text("rates.csv", "text/csv", "day,rate\n2026-11-01,512.3\n"),
    text("more notes.txt", "text/plain", "more"),
  ]);
  const attached = page.locator("[data-attached]");
  await expect(attached).toHaveCount(5);
  await expect(
    page.locator('[data-attached="inputs/more-notes.txt"]'),
  ).toContainText("text/plain");
  const refusals = page.locator('[data-field="attach-refusals"]');
  await input.setInputFiles([text("sixth.txt", "text/plain", "six")]);
  await expect(refusals).toHaveText("sixth.txt: only 5 files can be attached.");
  await expect(attached).toHaveCount(5);

  await page.getByRole("button", { name: "Remove more notes.txt" }).click();
  await expect(attached).toHaveCount(4);
  await input.setInputFiles([
    {
      name: "big.txt",
      mimeType: "text/plain",
      buffer: Buffer.alloc(1_048_577, 97),
    },
    text("report.pdf", "application/pdf", "%PDF-1.7"),
  ]);
  await expect(refusals).toContainText("big.txt: a file can be at most 1 MiB.");
  await expect(refusals).toContainText(
    "report.pdf: only plain text, markdown, JSON or CSV can be attached.",
  );
  await expect(attached).toHaveCount(4);
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(results.violations.map((violation) => violation.id)).toEqual([]);

  await page
    .getByRole("textbox", { name: "Goal" })
    .fill("Summarize the attached files");
  await page.getByRole("button", { name: "Run", exact: true }).click();
  await page.getByRole("link", { name: "Open this run" }).click();
  await expect(page).toHaveURL(/\/runs\/[0-9a-f-]{36}/);
  const runId = page.url().split("/").at(-1) ?? "";
  expect(probe(runId)).toEqual([
    { path: "inputs/data.json", media_type: "application/json", bytes: 8 },
    { path: "inputs/notes.txt", media_type: "text/plain", bytes: 11 },
    { path: "inputs/plan.md", media_type: "text/markdown", bytes: 6 },
    { path: "inputs/rates.csv", media_type: "text/csv", bytes: 26 },
  ]);

  // Attaching isn't a tool: the catalog's Files group is unchanged by it.
  const catalog = await (await page.request.get("/api/v1/tools")).json();
  const files = catalog.tools
    .filter((tool: { group: string }) => tool.group === "files")
    .map((tool: { tool_id: string }) => tool.tool_id)
    .sort();
  expect(files).toEqual([
    "publish_artifact",
    "read_csv",
    "read_run_file",
    "save_artifact",
    "store_remote_file",
  ]);
});
