import type { Page } from "@playwright/test";

import { csrfToken, expectRefusal } from "./support/api.ts";
import { signIn, users } from "./support/auth.ts";
import { arranged, need, webOrigin } from "./support/env.ts";
import { expect, test } from "./support/fixtures.ts";

// US-16.3 and Decision 0023 E3. Arranged by qualify_identity: member P belongs to workspace P, where a run
// reads "Only in workspace P", and to workspace G, where runs read "Spend fully reported". The foreign
// workspace is one P doesn't belong to. Runs-g belongs to G only.
const workspaces = arranged({
  p: "AUTOBOTS_TEST_MULTI_WORKSPACE_P",
  g: "AUTOBOTS_TEST_MULTI_WORKSPACE_G",
  foreign: "AUTOBOTS_TEST_FOREIGN_WORKSPACE",
});
const ONLY_P = "Only in workspace P";
const ONLY_G = "Spend fully reported";

async function choose(page: Page, name: string) {
  const chooser = page.getByLabel(/^(Choose a workspace|Workspace)$/);
  await Promise.all([
    page.waitForEvent("load"),
    chooser.selectOption({ label: name }),
  ]);
}

async function chosenCookie(page: Page): Promise<string | undefined> {
  return (await page.context().cookies()).find(
    (cookie) => cookie.name === "autobots.workspace",
  )?.value;
}

test("the arranged values are present", () => {
  for (const name of [
    "AUTOBOTS_WEB_URL",
    "AUTOBOTS_TEST_MULTI_EMAIL",
    "AUTOBOTS_TEST_MULTI_PASSWORD",
    "AUTOBOTS_TEST_MULTI_WORKSPACE_P",
    "AUTOBOTS_TEST_MULTI_WORKSPACE_G",
    "AUTOBOTS_TEST_FOREIGN_WORKSPACE",
    "AUTOBOTS_TEST_RUNS_EMAIL",
  ]) {
    expect(need(name)).not.toBe("");
  }
});

test("a member of two workspaces chooses one, works in it, and the choice survives a reload", async ({
  page,
}) => {
  await signIn(page, users.multi);
  const chooser = page.locator('[data-field="workspace-chooser"]');
  await expect(chooser).toBeVisible();
  await expect(chooser.getByText("Choose a workspace")).toBeVisible();
  await choose(page, "multi-p@example.invalid");
  await page.goto("/runs");
  await expect(page.getByText(ONLY_P)).toBeVisible();
  await expect(page.getByText(ONLY_G)).toHaveCount(0);
  await page.reload();
  await expect(page.getByText(ONLY_P)).toBeVisible();
  expect(await chosenCookie(page)).toBe(workspaces.p);
  const cookie = (await page.context().cookies()).find(
    (item) => item.name === "autobots.workspace",
  );
  expect(cookie?.httpOnly).toBe(true);
  expect(cookie?.sameSite).toBe("Strict");
});

test("changing the workspace changes what member screens show", async ({
  page,
}) => {
  await signIn(page, users.multi);
  await choose(page, "multi-p@example.invalid");
  await page.goto("/runs");
  await expect(page.getByText(ONLY_P)).toBeVisible();
  await choose(page, "runs-g@example.invalid");
  await page.goto("/runs");
  await expect(page.getByText(ONLY_G)).toBeVisible();
  await expect(page.getByText(ONLY_P)).toHaveCount(0);
  expect(await chosenCookie(page)).toBe(workspaces.g);
});

test("a chosen workspace the user doesn't belong to is refused, and nothing of it is returned", async ({
  page,
}) => {
  await signIn(page, users.multi);
  await page.context().addCookies([
    {
      name: "autobots.workspace",
      value: workspaces.foreign,
      url: webOrigin(),
      httpOnly: true,
      sameSite: "Strict",
    },
  ]);
  const reply = await page.request.get("/api/v1/runs");
  const body = await expectRefusal(reply, { status: 403, code: "forbidden" });
  expect(JSON.stringify(body)).not.toContain(workspaces.foreign);
  // The route itself never stores a workspace the session doesn't belong to.
  const token = await csrfToken(page);
  const set = await page.request.post("/api/workspace", {
    headers: { Origin: webOrigin(), [token.header]: token.token },
    data: { workspace_id: workspaces.foreign },
  });
  expect(set.status()).toBe(403);
});

test("setting the workspace needs the origin and CSRF token, and a refusal changes nothing", async ({
  page,
}) => {
  await signIn(page, users.multi);
  await choose(page, "multi-p@example.invalid");
  const missing = await page.request.post("/api/workspace", {
    headers: { Origin: webOrigin() },
    data: { workspace_id: workspaces.g },
  });
  await expectRefusal(missing, { status: 403, code: "missing_csrf" });
  const forged = await page.request.post("/api/workspace", {
    headers: { Origin: "http://evil.example" },
    data: { workspace_id: workspaces.g },
  });
  expect(forged.status()).toBe(403);
  expect(await chosenCookie(page)).toBe(workspaces.p);
});

test("a member of one workspace sees no chooser, and member screens work as before", async ({
  page,
}) => {
  await signIn(page, users.runs);
  await expect(page.locator('[data-field="workspace-chooser"]')).toHaveCount(0);
  await page.goto("/runs");
  await expect(page.getByText(ONLY_G).first()).toBeVisible();
  expect(await chosenCookie(page)).toBeUndefined();
});
