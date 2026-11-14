import {
  parseSessionSummary,
  parseWorkspaceSummary,
} from "@autobots/api-client";

import { expectNoA11yViolations } from "./support/a11y.ts";
import { getJson } from "./support/api.ts";
import { submitSignIn, users } from "./support/auth.ts";
import { arranged, screenshotPath } from "./support/env.ts";
import { expect, test } from "./support/fixtures.ts";
import { captureBodies } from "./support/leaks.ts";

// Each test signs in through the form itself and asserts what follows, as this suite covers the form.
const stack = arranged({
  workspaceA: "AUTOBOTS_TEST_WORKSPACE_A",
  workspaceB: "AUTOBOTS_TEST_WORKSPACE_B",
  serviceKey: "AUTOBOTS_TEST_SERVICE_KEY",
});
const SIGN_IN_UNAVAILABLE =
  "Signing in is unavailable right now. Check that the local services are running, then try again.";

test("the owner signs in through the form, and the API verifies identity and membership", async ({
  page,
  context,
}) => {
  const owner = users.owner;
  // Pages and their scripts, styles and fonts, whose bodies are each read before the check below.
  const bodies = captureBodies(
    page,
    (response) => response.request().resourceType() !== "fetch",
  );
  await submitSignIn(page, owner);
  await expect(
    page.getByText("Signed in, with access to 1 workspace."),
  ).toBeVisible();
  const cookie = (await context.cookies()).find(
    (item) => item.name === "autobots.session",
  );
  expect(cookie?.httpOnly).toBe(true);
  expect(cookie?.sameSite).toBe("Strict");
  expect(await page.evaluate(() => document.cookie)).not.toContain(
    "autobots.session",
  );
  expect(
    await page.evaluate(() => JSON.stringify({ ...localStorage })),
  ).not.toContain("access_token");
  const own = await getJson(page, {
    path: `/api/v1/workspaces/${stack.workspaceA}`,
    parse: parseWorkspaceSummary,
  });
  expect(own.id).toBe(stack.workspaceA);
  const me = await getJson(page, {
    path: "/api/v1/session",
    parse: parseSessionSummary,
  });
  expect(me.workspace_ids).toEqual([stack.workspaceA]);
  const other = await page.request.get(
    `/api/v1/workspaces/${stack.workspaceB}`,
  );
  expect(other.status()).toBe(403);
  const read = await bodies();
  expect(read.length, "the sign-in page's bodies were read").toBeGreaterThan(0);
  for (const reply of read) {
    expect(reply.body, reply.url).not.toContain(stack.serviceKey);
    expect(reply.body, reply.url).not.toContain(owner.password);
  }
  await page.screenshot({
    path: screenshotPath("signed-in.png"),
    fullPage: true,
  });
});

test("a wrong password shows a safe error, and no session", async ({
  page,
  context,
}) => {
  await submitSignIn(page, {
    email: users.owner.email,
    password: "not-the-password",
  });
  await expect(
    page.getByText("That email and password did not work."),
  ).toBeVisible();
  expect(
    (await context.cookies()).some((item) => item.name === "autobots.session"),
  ).toBe(false);
  expect(
    (await page.request.get(`/api/v1/workspaces/${stack.workspaceA}`)).status(),
  ).toBe(401);
  await page.screenshot({
    path: screenshotPath("sign-in-failed.png"),
    fullPage: true,
  });
});

test("signing out ends access", async ({ page }) => {
  await submitSignIn(page, users.owner);
  await expect(
    page.getByText("Signed in, with access to 1 workspace."),
  ).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByText("You are not signed in.")).toBeVisible();
  expect(
    (await page.request.get(`/api/v1/workspaces/${stack.workspaceA}`)).status(),
  ).toBe(401);
});

// Only a 401 is about the credentials (WSHL-07). The replies are arranged with page.route; the
// session route's own classification of an Auth outage is covered by boundary.spec.ts.
test("a sign-in that fails for any other reason says so, not that the password was wrong", async ({
  page,
  context,
}) => {
  let answer: "outage" | "no reply" | "refused" = "outage";
  await page.route("**/api/session", (route) => {
    if (route.request().method() !== "POST") return route.continue();
    if (answer === "no reply") return route.abort("connectionrefused");
    return route.fulfill(
      answer === "refused"
        ? {
            status: 403,
            json: {
              code: "forbidden_origin",
              message: "This request was refused.",
            },
          }
        : {
            status: 503,
            json: {
              code: "auth_unavailable",
              message: "The sign-in service is unavailable.",
            },
          },
    );
  });
  await page.goto("/sign-in");
  await page.getByLabel("Email").fill(users.owner.email);
  await page.getByLabel("Password").fill(users.owner.password);
  // Each case changes the sentence, so a stale one can't satisfy the next.
  for (const [arranged, sentence] of [
    ["outage", SIGN_IN_UNAVAILABLE],
    [
      "refused",
      "This request was refused. Reload the page, then sign in again.",
    ],
    ["no reply", SIGN_IN_UNAVAILABLE],
  ] as const) {
    answer = arranged;
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByText(sentence)).toBeVisible();
    await expect(
      page.getByText("That email and password did not work."),
    ).toHaveCount(0);
  }
  expect(
    (await context.cookies()).some((item) => item.name === "autobots.session"),
  ).toBe(false);
});

test("a sign-out that fails says so, and the person stays signed in", async ({
  page,
}) => {
  await submitSignIn(page, users.owner);
  await expect(
    page.getByText("Signed in, with access to 1 workspace."),
  ).toBeVisible();
  await page.route("**/api/session", (route) =>
    route.request().method() === "DELETE"
      ? route.fulfill({
          status: 503,
          json: {
            code: "server_misconfigured",
            message: "The web server is missing part of its configuration.",
          },
        })
      : route.continue(),
  );
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(
    page.getByText("Signing out did not finish. Try again."),
  ).toBeVisible();
  await expect(
    page.getByText("Signed in, with access to 1 workspace."),
  ).toBeVisible();
  await page.unroute("**/api/session");
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByText("You are not signed in.")).toBeVisible();
});

test("signing in needs the origin and CSRF checks", async ({ request }) => {
  const reply = await request.post("/api/session", {
    data: users.owner,
  });
  expect(reply.status()).toBe(403);
});

// US-15.2: member-c owns their own workspace and is a member of workspace A.
test("the account footer, the Account page and the display name", async ({
  page,
}) => {
  const member = users.member;
  await submitSignIn(page, member);
  await expect(
    page.getByText(/Signed in, with access to 2 workspaces/),
  ).toBeVisible();
  const local = member.email.split("@")[0] ?? "";
  const me = await getJson(page, {
    path: "/api/v1/session",
    parse: parseSessionSummary,
  });
  expect(me.display_name).toBe(local);
  expect(me.display_name_saved).toBe(false);
  expect(me.email).toBe(member.email);
  expect(me.workspaces).toHaveLength(2);
  expect(me.workspaces.map((item) => item.role).sort()).toEqual([
    "member",
    "owner",
  ]);
  for (const item of me.workspaces) expect(item.name.length).toBeGreaterThan(0);

  const footer = page.locator("[data-account]");
  await expect(footer.locator('[data-field="display-name"]')).toHaveText(local);
  // Decision 0023 E3: a member of two workspaces has none until they choose, then its role shows.
  await expect(footer.locator('[data-field="role"]')).toHaveText(
    "No workspace",
  );
  const chosen = me.workspaces[0];
  if (chosen === undefined) throw new Error("The session lists no workspace.");
  await Promise.all([
    page.waitForEvent("load"),
    page.getByLabel("Choose a workspace").selectOption({ label: chosen.name }),
  ]);
  await expect(footer.locator('[data-field="role"]')).toHaveText(
    chosen.role === "owner" ? "Owner" : "Member",
  );
  await expect(footer).toContainText("this Mac");
  await footer.locator("summary").click();
  await expect(footer.getByRole("link", { name: "Account" })).toBeVisible();
  await expect(footer.getByRole("button", { name: "Sign out" })).toBeVisible();
  await footer.getByRole("link", { name: "Account" }).click();
  await expect(page).toHaveURL(/\/settings\/account$/);

  await expect(
    page.getByRole("heading", { name: "Account", level: 1 }),
  ).toBeVisible();
  const field = page.getByLabel("Display name");
  await expect(field).toBeEditable();
  await expect(page.locator('[data-field="email"]')).toHaveText(member.email);
  await expect(page.locator("main")).toContainText("Owner");
  await expect(page.locator("main")).toContainText("Member");
  await expect(
    page.locator("main").getByRole("button", { name: "Sign out" }),
  ).toBeVisible();
  await expectNoA11yViolations(page);

  await field.fill("Cy Member");
  await page.getByRole("button", { name: "Save name" }).click();
  await expect(page.locator('[data-message="profile"]')).toHaveText("Saved.");
  await expect(footer.locator('[data-field="display-name"]')).toHaveText(
    "Cy Member",
  );
  for (const refused of ["", "x".repeat(61)]) {
    await field.fill(refused);
    await page.getByRole("button", { name: "Save name" }).click();
    await expect(page.locator('[data-message="profile"]')).toContainText(
      "needs 1 to 60 characters",
    );
  }
  const after = await getJson(page, {
    path: "/api/v1/session",
    parse: parseSessionSummary,
  });
  expect(after.display_name).toBe("Cy Member");
  expect(after.display_name_saved).toBe(true);
  await page.reload();
  await expect(footer.locator('[data-field="display-name"]')).toHaveText(
    "Cy Member",
  );
});
