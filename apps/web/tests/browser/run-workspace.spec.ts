import { parseEventPage, parseToolCatalog } from "@autobots/api-client";
import type { Page, Route } from "@playwright/test";

import { expectNoA11yViolations } from "./support/a11y.ts";
import { getJson } from "./support/api.ts";
import { signIn, users } from "./support/auth.ts";
import { arrayOf, objectOf, runDbHelper } from "./support/db-helpers.ts";
import { arranged } from "./support/env.ts";
import { expect, test } from "./support/fixtures.ts";
import { disconnectProviderKey, ensureProviderKey } from "./support/keys.ts";
import { expectNoPrivateValues } from "./support/leaks.ts";
import { admitRun, readRun, runCommand } from "./support/runs.ts";

const runs = arranged({
  loop: "AUTOBOTS_TEST_LOOP_RUN",
  gap: "AUTOBOTS_TEST_ARTIFACT_RUN",
});
// US-14.4, arranged by tests/db/checks/tool_use_view_check.py.
const tools = arranged({
  run: "AUTOBOTS_TEST_TOOL_RUN",
  execution: "AUTOBOTS_TEST_TOOL_EXECUTION",
  generation: "AUTOBOTS_TEST_TOOL_GENERATION",
  workspace: "AUTOBOTS_TEST_TOOL_WORKSPACE",
});
// US-17.4, arranged by tests/db/checks/tool_use_view_check.py: a browse_goal use with two steps.
const browse = arranged({ run: "AUTOBOTS_TEST_BROWSE_RUN" });
const RUN_NOT_FOUND =
  "That run is not available. Sign in with access to it, or check the link.";
const OUTAGE = {
  status: 503,
  json: {
    code: "service_unavailable",
    message: "The local API is unavailable.",
  },
};

/** Admits a plain run from Home. Admission needs a key, which ensureProviderKey arranges first. */
async function admitPlain(page: Page, label: string): Promise<string> {
  await page.goto("/");
  return admitRun(
    page,
    { goal_text: `Goal ${label}`, limit_micro_usd: 1000 },
    { key: `workspace-${label}` },
  );
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

test("events arrive live and survive a dropped connection without duplicates", async ({
  page,
}) => {
  await signIn(page, users.owner);
  await ensureProviderKey(page);
  const id = await admitPlain(page, "live");
  await page.goto(`/runs/${id}`);
  await expect(page.locator("[data-run-status]")).toHaveAttribute(
    "data-run-status",
    "queued",
  );
  await expect(page.locator("[data-connection]")).toHaveAttribute(
    "data-connection",
    "live",
  );

  expect(
    (
      await runCommand(page, {
        run: id,
        command: "pause",
        expectedVersion: 1,
        key: "l1",
      })
    ).status(),
  ).toBe(200);
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
  expect(
    (
      await runCommand(page, {
        run: id,
        command: "resume",
        expectedVersion: 2,
        key: "l2",
      })
    ).status(),
  ).toBe(200);
  expect(
    (
      await runCommand(page, {
        run: id,
        command: "pause",
        expectedVersion: 3,
        key: "l3",
      })
    ).status(),
  ).toBe(200);
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

  const later = await getJson(page, {
    path: `/api/v1/runs/${id}/events?after=3`,
    parse: parseEventPage,
  });
  expect(later.events.map((event) => event.sequence)).toEqual([4]);
  await page.reload();
  await expect(page.locator("[data-sequence]")).toHaveCount(4);
  await expect(page.locator("[data-run-status]")).toHaveAttribute(
    "data-run-status",
    "paused",
  );
});

test("closing the page does not change the run, and the end of a run ends the stream", async ({
  openContext,
}) => {
  const context = await openContext();
  const page = await context.newPage();
  await signIn(page, users.owner);
  await ensureProviderKey(page);
  const id = await admitPlain(page, "closing");
  const viewer = await context.newPage();
  await viewer.goto(`/runs/${id}`);
  await expect(viewer.locator("[data-connection]")).toHaveAttribute(
    "data-connection",
    "live",
  );
  await viewer.close();
  const summary = await readRun(page, id);
  expect(summary.status).toBe("queued");
  expect(summary.version).toBe(1);
  const again = await context.newPage();
  await again.goto(`/runs/${id}`);
  await expect(again.locator("[data-connection]")).toHaveAttribute(
    "data-connection",
    "live",
  );
  expect(
    (
      await runCommand(page, {
        run: id,
        command: "cancel",
        expectedVersion: 1,
        key: "c1",
      })
    ).status(),
  ).toBe(200);
  await expect(again.locator("[data-run-status]")).toHaveAttribute(
    "data-run-status",
    "cancelled",
  );
  await expect(again.locator("[data-connection]")).toHaveAttribute(
    "data-connection",
    "ended",
    { timeout: 10_000 },
  );
});

test("a plan, its evidence, a reason and artifacts show, sanitized, in both themes", async ({
  page,
}) => {
  await signIn(page, users.owner);
  await page.goto(`/runs/${runs.loop}`);
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

  expectNoPrivateValues(await page.content(), {
    label: "the run page",
    extra: ["checkpoint", "object_path", "policy_snapshot"],
  });
  const replay = await (
    await page.request.get(`/api/v1/runs/${runs.loop}/events?after=0`)
  ).text();
  expect(replay).not.toContain("PROTECTED-REASONING");
  const workspace = await (
    await page.request.get(`/api/v1/runs/${runs.loop}/workspace`)
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
    await expectNoA11yViolations(page);
  }
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to content" }),
  ).toBeFocused();
});

test("retained events that can't fill the range say so, and the status comes from the snapshot", async ({
  page,
}) => {
  await signIn(page, users.owner);
  const page1 = await getJson(page, {
    path: `/api/v1/runs/${runs.gap}/events?after=0`,
    parse: parseEventPage,
  });
  expect(page1.gap).toBe(true);
  await page.goto(`/runs/${runs.gap}`);
  await expect(page.locator("[data-gap]")).toBeVisible();
  await expect(page.locator("[data-run-status]")).toBeVisible();
  await expect(page.locator('[data-sequence="1"]')).toHaveCount(0);
  await expect(page.locator('[data-sequence="3"]')).toContainText("published");
});

test("another workspace gets a clear refusal", async ({ page }) => {
  await signIn(page, users.ownerB);
  const asked = runRequests(page, runs.loop);
  await page.goto(`/runs/${runs.loop}`);
  const state = page.locator('[data-state="unavailable"]');
  await expect(state).toBeVisible();
  // R-28: a missing run says so once. Nothing reads it again, and no stream opens.
  await expect(state).toHaveAttribute("data-reason", "not_found");
  await expect(state.getByRole("alert")).toHaveText(RUN_NOT_FOUND);
  await expect(state.getByRole("button", { name: "Retry" })).toHaveCount(0);
  // Longer than the first two attempts would take, had it kept trying.
  await page.waitForTimeout(3_500);
  expect(asked).toEqual([`/api/v1/runs/${runs.loop}/workspace`]);
  expect(
    (
      await page.request.get(`/api/v1/runs/${runs.loop}/events?after=0`)
    ).status(),
  ).toBe(404);
  expect(
    (
      await page.request.get(`/api/v1/runs/${runs.loop}/events/stream?after=0`)
    ).status(),
  ).toBe(404);
  expect(
    (await page.request.get(`/api/v1/runs/${runs.loop}/workspace`)).status(),
  ).toBe(404);
});

// R-28: a refusal, a malformed id and a drifted reply each say so once and stop: no Retry, no
// further reads and no stream. The replies are arranged with page.route on the snapshot read.
test("a refusal, a malformed id and a drifted reply each stop the run page", async ({
  page,
}) => {
  await signIn(page, users.owner);
  const asked = runRequests(page, runs.loop);
  const logged: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") logged.push(message.text());
  });
  let arranged: Parameters<Route["fulfill"]>[0] = OUTAGE;
  await page.route(snapshotOf(runs.loop), (route) => route.fulfill(arranged));
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
    await page.goto(`/runs/${runs.loop}`);
    await expect(state).toHaveAttribute("data-reason", reason);
    await expect(state.getByRole("alert")).toHaveText(words);
    await expect(state.getByRole("button", { name: "Retry" })).toHaveCount(0);
    await expect(page.locator('[data-field="retry-in"]')).toHaveCount(0);
    // Longer than the first two attempts would take, had it kept trying.
    await page.waitForTimeout(3_500);
    expect(asked).toEqual([`/api/v1/runs/${runs.loop}/workspace`]);
  }
  expect(
    logged.some((line) =>
      line.includes("This page and the local service disagree."),
    ),
  ).toBe(true);
  await page.unroute(snapshotOf(runs.loop));

  // The API's own reply to an id that isn't a UUID, unarranged.
  await page.goto("/runs/not-a-run");
  await expect(state).toHaveAttribute("data-reason", "not_found");
  await expect(state.getByRole("alert")).toHaveText(RUN_NOT_FOUND);
});

// R-28: an outage is tried again after 1, 2 and 4 seconds, saying when, and Retry reads at once.
test("an outage backs off with a visible Retry, and the run shows when it recovers", async ({
  page,
}) => {
  await signIn(page, users.owner);
  const times: number[] = [];
  let failing = 2;
  await page.route(snapshotOf(runs.loop), (route) => {
    times.push(Date.now());
    if (failing === 0) return route.continue();
    failing -= 1;
    return route.fulfill(OUTAGE);
  });
  await page.goto(`/runs/${runs.loop}`);
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
  await page.unroute(snapshotOf(runs.loop));
});

// R-28: snapshot reads run one at a time, and a reply older than the snapshot shown is discarded.
// The first read after the route is installed is held, then answered with a snapshot older than
// the page's (cursor 0, with a status this run never reaches), as a reply that lost a race would
// be. Later reads go through.
test("an older snapshot reply that arrives late never replaces a newer one", async ({
  page,
}) => {
  await signIn(page, users.owner);
  await ensureProviderKey(page);
  const id = await admitPlain(page, "order");
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
  expect(
    (
      await runCommand(page, {
        run: id,
        command: "pause",
        expectedVersion: 1,
        key: "o1",
      })
    ).status(),
  ).toBe(200);
  expect(
    (
      await runCommand(page, {
        run: id,
        command: "resume",
        expectedVersion: 2,
        key: "o2",
      })
    ).status(),
  ).toBe(200);
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
    (await request.get(`/api/v1/runs/${runs.loop}/events/stream`)).status(),
  ).toBe(401);
  await signIn(page, users.owner);
  await ensureProviderKey(page);
  await admitPlain(page, "link");
  await page.getByRole("textbox", { name: "Goal" }).fill("Open what I started");
  await page.getByRole("button", { name: "Run", exact: true }).click();
  await page.getByRole("link", { name: "Open this run" }).click();
  await expect(page).toHaveURL(/\/runs\//);
  await expect(
    page.getByRole("region", { name: "Goal" }).getByRole("paragraph"),
  ).toHaveText("Open what I started");
  // Disconnected again. A later test here saves it once more, and runs.spec.ts removes that one
  // before settings.spec.ts checks that workspace A has none (TWEB-01).
  await disconnectProviderKey(page);
});

test("US-17.4: a browse's steps show their screenshots, pages and submits, only to a member", async ({
  page,
  request,
}) => {
  expect(
    (
      await request.get(`/api/v1/runs/${browse.run}/tool-uses/1/steps`)
    ).status(),
  ).toBe(401);
  expect(
    (
      await request.get(
        `/api/v1/runs/${browse.run}/tool-uses/1/steps/1/screenshot`,
      )
    ).status(),
  ).toBe(401);
  await signIn(page, users.owner);
  await page.goto(`/runs/${browse.run}`);
  const section = page.getByRole("region", { name: "Tools used" });
  const row = section.locator('[data-tool-id="browse_goal"]');
  await expect(row).toHaveCount(1);
  await row.getByText("Show 2 steps").click();
  const steps = row.locator("[data-browse-step]");
  await expect(steps).toHaveCount(2);
  await expect(steps.nth(0)).toContainText("Step 1: example.com/");
  await expect(steps.nth(1)).toContainText("Step 2: example.com/search");
  await expect(steps.nth(1)).toContainText("Submitted to example.com/search");
  // US-20.3: what a stealth browse's step pressed and typed into, and none on the step before it.
  await expect(steps.nth(1)).toContainText('Typed into "Search", text input');
  await expect(steps.nth(1)).toContainText("Pressed an unnamed button");
  await expect(steps.nth(0)).not.toContainText("Pressed");
  await expect(row).not.toContainText("secret");
  const image = steps.nth(1).getByRole("img", {
    name: "Screenshot after step 2, on example.com/search",
  });
  await expect(image).toBeVisible();
  await expect
    .poll(() =>
      image.evaluate((img: HTMLImageElement) =>
        img.complete ? img.naturalWidth : 0,
      ),
    )
    .toBe(320);
  await expectNoA11yViolations(page);
});

test("US-14.4: tool uses show live, once each and in order, and again after a reload", async ({
  page,
}) => {
  await signIn(page, users.owner);
  await page.goto(`/runs/${tools.run}`);
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
  const made = await runDbHelper(
    "tool_use_live.py",
    [tools.run, tools.generation, tools.workspace],
    objectOf({ outcome: "string" }),
  );
  expect(made.outcome).toBe("succeeded");
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
  await expectNoA11yViolations(page);

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
  await signIn(page, users.owner);
  await page.goto(`/workflow-executions/${tools.execution}`);
  const read = page.locator('[data-node-tools="read"]');
  await expect(read.getByRole("heading", { name: "Node read" })).toBeVisible();
  await expect(read.locator('[data-tool-id="read_run_file"]')).toHaveCount(1);
  await expect(read.locator("[data-tool-use]")).toHaveCount(1);
  const save = page.locator('[data-node-tools="save"]');
  await expect(save.locator('[data-tool-id="save_artifact"]')).toHaveCount(1);
  await expect(save.locator('[data-tool-id="read_run_file"]')).toHaveCount(0);
  await expect(page.locator('[data-node-tools="in"]')).toHaveCount(0);
  await expectNoA11yViolations(page);

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

/** The run's input files, as tests/db/arrange/run_files_probe.py reads them from the database. */
function probe(
  runId: string,
): Promise<{ path: string; media_type: string; bytes: number }[]> {
  return runDbHelper(
    "run_files_probe.py",
    [runId],
    arrayOf(
      objectOf({ path: "string", media_type: "string", bytes: "number" }),
    ),
  );
}

test("US-14.9: up to five text files attach to a goal as run inputs, and the rest are refused", async ({
  page,
}) => {
  await signIn(page, users.owner);
  await ensureProviderKey(page);
  await admitPlain(page, `attach-${Date.now()}`);
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
  await expectNoA11yViolations(page);

  await page
    .getByRole("textbox", { name: "Goal" })
    .fill("Summarize the attached files");
  await page.getByRole("button", { name: "Run", exact: true }).click();
  await page.getByRole("link", { name: "Open this run" }).click();
  await expect(page).toHaveURL(/\/runs\/[0-9a-f-]{36}/);
  const runId = page.url().split("/").at(-1) ?? "";
  expect(await probe(runId)).toEqual([
    { path: "inputs/data.json", media_type: "application/json", bytes: 8 },
    { path: "inputs/notes.txt", media_type: "text/plain", bytes: 11 },
    { path: "inputs/plan.md", media_type: "text/markdown", bytes: 6 },
    { path: "inputs/rates.csv", media_type: "text/csv", bytes: 26 },
  ]);

  // Attaching isn't a tool: the catalog's Files group is unchanged by it.
  const catalog = await getJson(page, {
    path: "/api/v1/tools",
    parse: parseToolCatalog,
  });
  const files = catalog.tools
    .filter((tool) => tool.group === "files")
    .map((tool) => tool.tool_id)
    .sort();
  expect(files).toEqual([
    "append_to_file",
    "publish_artifact",
    "read_artifact",
    "read_csv",
    "read_run_file",
    "save_artifact",
    "store_remote_file",
  ]);
});
