import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const OWNER_EMAIL = process.env.AUTOBOTS_TEST_OWNER_EMAIL ?? "";
const OWNER_PASSWORD = process.env.AUTOBOTS_TEST_OWNER_PASSWORD ?? "";
const WORKSPACE_A = process.env.AUTOBOTS_TEST_WORKSPACE_A ?? "";
const WORKSPACE_B = process.env.AUTOBOTS_TEST_WORKSPACE_B ?? "";
const SERVICE_KEY = process.env.AUTOBOTS_TEST_SERVICE_KEY ?? "";
const MEMBER_EMAIL = process.env.AUTOBOTS_TEST_MEMBER_EMAIL ?? "";
const MEMBER_PASSWORD = process.env.AUTOBOTS_TEST_MEMBER_PASSWORD ?? "";
const SIGN_IN_UNAVAILABLE =
  "Signing in is unavailable right now. Check that the local services are running, then try again.";

async function signIn(
  page: Page,
  email: string,
  password: string,
): Promise<void> {
  await page.goto("/sign-in");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

test("the owner signs in through the form, and the API verifies identity and membership", async ({
  page,
  context,
}) => {
  const bodies: string[] = [];
  page.on("response", async (response) => {
    if (response.request().resourceType() !== "fetch")
      bodies.push(await response.text().catch(() => ""));
  });
  await signIn(page, OWNER_EMAIL, OWNER_PASSWORD);
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
  const own = await page.request.get(`/api/v1/workspaces/${WORKSPACE_A}`);
  expect(own.status()).toBe(200);
  expect((await own.json()).id).toBe(WORKSPACE_A);
  const me = await (await page.request.get("/api/v1/session")).json();
  expect(me.workspace_ids).toEqual([WORKSPACE_A]);
  const other = await page.request.get(`/api/v1/workspaces/${WORKSPACE_B}`);
  expect(other.status()).toBe(403);
  for (const body of bodies) {
    expect(body).not.toContain(SERVICE_KEY);
    expect(body).not.toContain(OWNER_PASSWORD);
  }
  await page.screenshot({
    path: `${process.env.AUTOBOTS_WEB_SCREENSHOTS}/signed-in.png`,
    fullPage: true,
  });
});

test("a wrong password shows a safe error, and no session", async ({
  page,
  context,
}) => {
  await signIn(page, OWNER_EMAIL, "not-the-password");
  await expect(
    page.getByText("That email and password did not work."),
  ).toBeVisible();
  expect(
    (await context.cookies()).some((item) => item.name === "autobots.session"),
  ).toBe(false);
  expect(
    (await page.request.get(`/api/v1/workspaces/${WORKSPACE_A}`)).status(),
  ).toBe(401);
  await page.screenshot({
    path: `${process.env.AUTOBOTS_WEB_SCREENSHOTS}/sign-in-failed.png`,
    fullPage: true,
  });
});

test("signing out ends access", async ({ page }) => {
  await signIn(page, OWNER_EMAIL, OWNER_PASSWORD);
  await expect(
    page.getByText("Signed in, with access to 1 workspace."),
  ).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByText("You are not signed in.")).toBeVisible();
  expect(
    (await page.request.get(`/api/v1/workspaces/${WORKSPACE_A}`)).status(),
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
  await page.getByLabel("Email").fill(OWNER_EMAIL);
  await page.getByLabel("Password").fill(OWNER_PASSWORD);
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
  await signIn(page, OWNER_EMAIL, OWNER_PASSWORD);
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
    data: { email: OWNER_EMAIL, password: OWNER_PASSWORD },
  });
  expect(reply.status()).toBe(403);
});

// US-15.2: member-c owns their own workspace and is a member of workspace A.
test("the account footer, the Account page and the display name", async ({
  page,
}) => {
  await signIn(page, MEMBER_EMAIL, MEMBER_PASSWORD);
  await expect(
    page.getByText(/Signed in, with access to 2 workspaces/),
  ).toBeVisible();
  const local = MEMBER_EMAIL.split("@")[0] ?? "";
  const me = await (await page.request.get("/api/v1/session")).json();
  expect(me.display_name).toBe(local);
  expect(me.display_name_saved).toBe(false);
  expect(me.email).toBe(MEMBER_EMAIL);
  expect(me.workspaces).toHaveLength(2);
  expect(
    me.workspaces.map((item: { role: string }) => item.role).sort(),
  ).toEqual(["member", "owner"]);
  for (const item of me.workspaces as { name: string }[])
    expect(item.name.length).toBeGreaterThan(0);

  const footer = page.locator("[data-account]");
  await expect(footer.locator('[data-field="display-name"]')).toHaveText(local);
  // Decision 0023 E3: a member of two workspaces has none until they choose, then its role shows.
  await expect(footer.locator('[data-field="role"]')).toHaveText(
    "No workspace",
  );
  const chosen = me.workspaces[0] as { name: string; role: string };
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
  await expect(page.locator('[data-field="email"]')).toHaveText(MEMBER_EMAIL);
  await expect(page.locator("main")).toContainText("Owner");
  await expect(page.locator("main")).toContainText("Member");
  await expect(
    page.locator("main").getByRole("button", { name: "Sign out" }),
  ).toBeVisible();
  const axe = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(axe.violations.map((item) => item.id)).toEqual([]);

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
  const after = await (await page.request.get("/api/v1/session")).json();
  expect(after.display_name).toBe("Cy Member");
  expect(after.display_name_saved).toBe(true);
  await page.reload();
  await expect(footer.locator('[data-field="display-name"]')).toHaveText(
    "Cy Member",
  );
});
