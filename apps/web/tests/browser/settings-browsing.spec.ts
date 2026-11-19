import {
  parseBrowsingSettingsView,
  parseExpertView,
  parseKeysAndVars,
  parseSessionSummary,
  parseToolCatalog,
  type BrowsingSettingsView,
} from "@autobots/api-client";
import type { Page } from "@playwright/test";

import { expectNoA11yViolations } from "./support/a11y.ts";
import { csrfHeaders, expectRefusal, getJson, send } from "./support/api.ts";
import { signIn, users } from "./support/auth.ts";
import { objectOf, runDbHelper } from "./support/db-helpers.ts";
import { expect, test } from "./support/fixtures.ts";

// US-17.1 and Decision 0035 Y1 to Y4, against the disposable identity stack. Settings → Browsing
// holds the workspace's YOLO setting, on by default; only the owner changes it; Home tells the
// owner once. Each test leaves YOLO on, as every other suite expects.

const ROUTE = "/api/settings/browsing";
const LABEL = "Let browsing type and submit (YOLO)";

async function setting(page: Page): Promise<BrowsingSettingsView> {
  const reply = await page.request.get(ROUTE);
  expect(reply.status()).toBe(200);
  return parseBrowsingSettingsView(await reply.json());
}

async function ownedWorkspace(page: Page): Promise<string> {
  const reply = await page.request.get("/api/v1/session");
  expect(reply.status()).toBe(200);
  const owned = parseSessionSummary(await reply.json()).workspaces.find(
    (workspace) => workspace.role === "owner",
  );
  if (owned === undefined) throw new Error("the owner owns no workspace");
  return owned.id;
}

test("a member sees YOLO on and can't change it", async ({ page }) => {
  await signIn(page, users.reader);
  await page.goto("/settings/browsing");
  const box = page.getByRole("checkbox", { name: LABEL });
  await expect(box).toBeChecked();
  await expect(box).toBeDisabled();
  await expect(
    page.getByText("Only the workspace owner can change this setting."),
  ).toBeVisible();
  await expectNoA11yViolations(page);
  const before = await setting(page);
  expect(before).toMatchObject({ yolo: true, viewer_can_change: false });
  await expectRefusal(
    await page.request.put(ROUTE, {
      headers: await csrfHeaders(page),
      data: { yolo: false, expected_version: before.version },
    }),
    { status: 403, code: "owner_required" },
  );
  expect((await setting(page)).yolo).toBe(true);
});

test("the owner turns YOLO off and on in Settings → Browsing", async ({
  page,
}) => {
  await signIn(page, users.owner);
  await page.goto("/settings");
  await page
    .getByRole("navigation", { name: "Settings sections" })
    .getByRole("link", { name: "Browsing", exact: true })
    .click();
  await expect(page).toHaveURL(/\/settings\/browsing$/);
  const box = page.getByRole("checkbox", { name: LABEL });
  await expect(box).toBeChecked();
  await expect(box).toBeEnabled();
  await expect(
    page.getByText("While this is on, a browse starts without asking you"),
  ).toBeVisible();
  await box.uncheck();
  await expect(page.getByRole("status")).toHaveText("YOLO is off.");
  expect((await setting(page)).yolo).toBe(false);
  await box.check();
  await expect(page.getByRole("status")).toHaveText("YOLO is on.");
  expect((await setting(page)).yolo).toBe(true);
  await expectNoA11yViolations(page);
});

test("Home tells the owner once that YOLO is on", async ({ page }) => {
  await signIn(page, users.owner);
  const workspace = await ownedWorkspace(page);
  await runDbHelper(
    "browsing_yolo.py",
    ["unseen", workspace],
    objectOf({ action: "string" }),
  );
  expect((await setting(page)).notice_pending).toBe(true);
  const read = (target: Page) =>
    target.waitForResponse(
      (reply) =>
        reply.url().endsWith(ROUTE) && reply.request().method() === "GET",
    );
  const first = read(page);
  await page.goto("/");
  await first;
  const notice = page.locator('[data-field="browsing-notice"]');
  await expect(notice).toContainText("Browsing's YOLO setting is on");
  await expect(
    notice.getByRole("link", { name: "Change it in Settings → Browsing" }),
  ).toHaveAttribute("href", "/settings/browsing");
  await expectNoA11yViolations(page);
  await expect
    .poll(async () => (await setting(page)).notice_pending)
    .toBe(false);
  const second = read(page);
  await page.goto("/");
  await second;
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(notice).toHaveCount(0);
});

test("the owner lists an Expert's browse domains in the editor, and saving makes a new version", async ({
  page,
}) => {
  await signIn(page, users.owner);
  // Arranged: an Expert can grant browse_goal only while browsing is on and the executor reports
  // qualified, so browsing is turned on for this workspace in Keys & vars, then removed again.
  const vars = "/api/settings/keys-and-vars";
  const switchOf = async () =>
    parseKeysAndVars(await (await page.request.get(vars)).json()).items.find(
      (item) => item.name === "browser_executor",
    );
  const before = await switchOf();
  expect(
    (
      await page.request.put(`${vars}/browser_executor`, {
        headers: await csrfHeaders(page),
        data: { value: "enabled", expected_version: before?.version ?? 0 },
      })
    ).status(),
  ).toBe(200);
  try {
    const catalog = await getJson(page, {
      path: "/api/v1/tools",
      parse: parseToolCatalog,
    });
    const browse = catalog.tools.find((tool) => tool.tool_id === "browse_goal");
    test.skip(
      browse?.availability !== "available",
      "the browser executor isn't qualified on this machine, so no Expert can grant browse_goal",
    );
    const made = await send(page, {
      path: "/api/v1/experts",
      data: { name: "Guide", config: { tools: ["browse_goal"] } },
      status: 201,
      parse: parseExpertView,
    });
    await page.goto(`/experts/${made.id}`);
    const field = page.getByLabel("Browse domains");
    await expect(field).toHaveValue("");
    await field.fill("en.wikivoyage.org");
    await page.getByRole("button", { name: "Save revision" }).click();
    await expect(page.locator('[data-message="save"]')).toContainText(
      "Saved as version 2",
    );
    await expectNoA11yViolations(page);
    const saved = await getJson(page, {
      path: `/api/v1/experts/${made.id}`,
      parse: parseExpertView,
    });
    expect(
      saved.versions.map((version) => version.config.browse_domains ?? []),
    ).toEqual([[], ["en.wikivoyage.org"]]);
  } finally {
    const after = await switchOf();
    expect(
      (
        await page.request.delete(`${vars}/browser_executor`, {
          headers: await csrfHeaders(page),
          data: { expected_version: after?.version ?? 0 },
        })
      ).status(),
    ).toBe(200);
  }
});
