import { expect, test, type Page } from "@playwright/test";

// US-16.3 and Decision 0023 E3. Arranged by qualify_identity: member P belongs to workspace P, where a run
// reads "Only in workspace P", and to workspace G, where runs read "Spend fully reported". The foreign
// workspace is one P doesn't belong to. Runs-g belongs to G only.
const ORIGIN = process.env.AUTOBOTS_WEB_URL ?? "";
const EMAIL = process.env.AUTOBOTS_TEST_MULTI_EMAIL ?? "";
const PASSWORD = process.env.AUTOBOTS_TEST_MULTI_PASSWORD ?? "";
const WORKSPACE_P = process.env.AUTOBOTS_TEST_MULTI_WORKSPACE_P ?? "";
const WORKSPACE_G = process.env.AUTOBOTS_TEST_MULTI_WORKSPACE_G ?? "";
const FOREIGN = process.env.AUTOBOTS_TEST_FOREIGN_WORKSPACE ?? "";
const SINGLE_EMAIL = process.env.AUTOBOTS_TEST_RUNS_EMAIL ?? "";
const SINGLE_PASSWORD = process.env.AUTOBOTS_TEST_RUNS_PASSWORD ?? "";
const ONLY_P = "Only in workspace P";
const ONLY_G = "Spend fully reported";

async function signIn(page: Page, email: string, password: string) {
  await page.goto("/sign-in");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText(/Signed in, with access to/)).toBeVisible();
}

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
  for (const value of [
    ORIGIN,
    EMAIL,
    PASSWORD,
    WORKSPACE_P,
    WORKSPACE_G,
    FOREIGN,
    SINGLE_EMAIL,
  ]) {
    expect(value).not.toBe("");
  }
});

test("a member of two workspaces chooses one, works in it, and the choice survives a reload", async ({
  page,
}) => {
  await signIn(page, EMAIL, PASSWORD);
  const chooser = page.locator('[data-field="workspace-chooser"]');
  await expect(chooser).toBeVisible();
  await expect(chooser.getByText("Choose a workspace")).toBeVisible();
  await choose(page, "multi-p@example.invalid");
  await page.goto("/runs");
  await expect(page.getByText(ONLY_P)).toBeVisible();
  await expect(page.getByText(ONLY_G)).toHaveCount(0);
  await page.reload();
  await expect(page.getByText(ONLY_P)).toBeVisible();
  expect(await chosenCookie(page)).toBe(WORKSPACE_P);
  const cookie = (await page.context().cookies()).find(
    (item) => item.name === "autobots.workspace",
  );
  expect(cookie?.httpOnly).toBe(true);
  expect(cookie?.sameSite).toBe("Strict");
});

test("changing the workspace changes what member screens show", async ({
  page,
}) => {
  await signIn(page, EMAIL, PASSWORD);
  await choose(page, "multi-p@example.invalid");
  await page.goto("/runs");
  await expect(page.getByText(ONLY_P)).toBeVisible();
  await choose(page, "runs-g@example.invalid");
  await page.goto("/runs");
  await expect(page.getByText(ONLY_G)).toBeVisible();
  await expect(page.getByText(ONLY_P)).toHaveCount(0);
  expect(await chosenCookie(page)).toBe(WORKSPACE_G);
});

test("a chosen workspace the user doesn't belong to is refused, and nothing of it is returned", async ({
  page,
}) => {
  await signIn(page, EMAIL, PASSWORD);
  await page.context().addCookies([
    {
      name: "autobots.workspace",
      value: FOREIGN,
      url: ORIGIN,
      httpOnly: true,
      sameSite: "Strict",
    },
  ]);
  const reply = await page.request.get("/api/v1/runs");
  expect(reply.status()).toBe(403);
  const body = (await reply.json()) as { code: string };
  expect(body.code).toBe("forbidden");
  expect(JSON.stringify(body)).not.toContain(FOREIGN);
  // The route itself never stores a workspace the session doesn't belong to.
  const token = (await (await page.request.get("/api/csrf")).json()) as {
    header: string;
    token: string;
  };
  const set = await page.request.post("/api/workspace", {
    headers: { Origin: ORIGIN, [token.header]: token.token },
    data: { workspace_id: FOREIGN },
  });
  expect(set.status()).toBe(403);
});

test("setting the workspace needs the origin and CSRF token, and a refusal changes nothing", async ({
  page,
}) => {
  await signIn(page, EMAIL, PASSWORD);
  await choose(page, "multi-p@example.invalid");
  const missing = await page.request.post("/api/workspace", {
    headers: { Origin: ORIGIN },
    data: { workspace_id: WORKSPACE_G },
  });
  expect(missing.status()).toBe(403);
  expect(((await missing.json()) as { code: string }).code).toBe(
    "missing_csrf",
  );
  const forged = await page.request.post("/api/workspace", {
    headers: { Origin: "http://evil.example" },
    data: { workspace_id: WORKSPACE_G },
  });
  expect(forged.status()).toBe(403);
  expect(await chosenCookie(page)).toBe(WORKSPACE_P);
});

test("a member of one workspace sees no chooser, and member screens work as before", async ({
  page,
}) => {
  await signIn(page, SINGLE_EMAIL, SINGLE_PASSWORD);
  await expect(page.locator('[data-field="workspace-chooser"]')).toHaveCount(0);
  await page.goto("/runs");
  await expect(page.getByText(ONLY_G).first()).toBeVisible();
  expect(await chosenCookie(page)).toBeUndefined();
});
