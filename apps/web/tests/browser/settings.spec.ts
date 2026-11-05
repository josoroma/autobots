import { readFileSync } from "node:fs";

import { expect, test, type Page } from "@playwright/test";

const EMAIL_A = process.env.AUTOBOTS_TEST_OWNER_EMAIL ?? "";
const PASSWORD_A = process.env.AUTOBOTS_TEST_OWNER_PASSWORD ?? "";
const EMAIL_B = process.env.AUTOBOTS_TEST_OWNER_B_EMAIL ?? "";
const PASSWORD_B = process.env.AUTOBOTS_TEST_OWNER_B_PASSWORD ?? "";
const EMAIL_C = process.env.AUTOBOTS_TEST_MEMBER_EMAIL ?? "";
const PASSWORD_C = process.env.AUTOBOTS_TEST_MEMBER_PASSWORD ?? "";
const WORKSPACE_A = process.env.AUTOBOTS_TEST_WORKSPACE_A ?? "";
const CATALOG_DOWN = process.env.AUTOBOTS_TEST_CATALOG_DOWN ?? "";
const CREDENTIAL = "/api/settings/model-providers/openrouter/credential";
const DRAFT = "Summarize the quarterly notes";
const VALID = "sk-or-valid-arranged-first";

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

async function csrf(page: Page): Promise<Record<string, string>> {
  const token = await (await page.request.get("/api/csrf")).json();
  return {
    [token.header]: token.token,
    Origin: new URL(page.url()).origin,
    "Content-Type": "application/json",
  };
}

async function status(page: Page): Promise<Record<string, unknown>> {
  return (await page.request.get("/api/settings/model-providers")).json();
}

async function submitKey(page: Page, key: string): Promise<void> {
  await page.getByLabel(/API key|Replace key/).fill(key);
  await page.getByRole("button", { name: "Save & validate" }).click();
}

test("without a key, local work stays usable and a model call is credentials_required, with the draft kept", async ({
  page,
}) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
  await page.getByRole("textbox", { name: "Goal" }).fill(DRAFT);
  const intents: string[] = [];
  page.on("request", (request) => {
    if (request.url().endsWith("/api/v1/runs")) intents.push(request.method());
  });
  await page.getByRole("button", { name: "Run" }).click();
  await expect(
    page.locator('[data-outcome="credentials_required"]'),
  ).toBeVisible();
  expect(intents).toEqual(["POST"]);
  await expect(page.getByRole("textbox", { name: "Goal" })).toHaveValue(DRAFT);
  for (const path of ["/settings", "/settings/models", "/"]) {
    await page.goto(path);
    await expect(page.locator("main")).toBeVisible();
  }
  await page.goto("/settings/models");
  await expect(page.locator('[data-field="source"]')).toHaveText("None");
  await expect(page.locator('[data-field="auth"]')).toContainText(
    "No key is configured",
  );
  await page.screenshot({
    path: `${process.env.AUTOBOTS_WEB_SCREENSHOTS}/models-missing.png`,
    fullPage: true,
  });
});

test("a rejected or uncheckable draft changes nothing and does not say more than it should", async ({
  page,
}) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
  await page.goto("/settings/models");
  await submitKey(page, "sk-or-reject-arranged");
  await expect(page.getByRole("status")).toContainText("was not accepted");
  await expect(page.getByLabel("API key")).toHaveValue("");
  expect((await status(page)).source).toBe("none");
  await submitKey(page, "sk-or-down-arranged");
  await expect(page.getByRole("status")).toContainText("could not be checked");
  expect((await status(page)).source).toBe("none");
});

test("Save and validate encrypts, keeps statuses separate, returns to the draft and starts nothing", async ({
  page,
}) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
  await page.getByRole("textbox", { name: "Goal" }).fill(DRAFT);
  await page.goto("/settings/models");
  const bodies: string[] = [];
  const requests: string[] = [];
  page.on("response", async (response) =>
    bodies.push(await response.text().catch(() => "")),
  );
  page.on("request", (request) => requests.push(request.url()));
  await submitKey(page, VALID);
  await expect(page.locator('[data-field="auth"]')).toHaveText(
    "The key authenticated.",
  );
  await expect(page.getByLabel("Replace key")).toHaveValue("");
  await expect(page.locator('[data-field="source"]')).toContainText(
    "encrypted",
  );
  await expect(page.locator('[data-field="catalog"]')).toHaveText("Available");
  await expect(page.locator('[data-field="qualification"]')).toContainText(
    "Not qualified",
  );
  await expect(page.locator('[data-field="version"]')).toHaveText("1");
  await page.waitForTimeout(200);
  for (const body of bodies) expect(body).not.toContain(VALID);
  const stored = await page.evaluate(() =>
    JSON.stringify({
      ...localStorage,
      ...sessionStorage,
      cookie: document.cookie,
    }),
  );
  expect(stored).not.toContain(VALID);
  await page.screenshot({
    path: `${process.env.AUTOBOTS_WEB_SCREENSHOTS}/models-configured.png`,
    fullPage: true,
  });
  await page.getByRole("link", { name: "Return to your draft" }).click();
  await expect(page.getByRole("textbox", { name: "Goal" })).toHaveValue(DRAFT);
  await page.waitForTimeout(300);
  expect(requests.filter((url) => url.includes("/runs/"))).toEqual([]);
});

test("a bad replacement keeps the prior key, and a stale write is a conflict with no secret", async ({
  page,
}) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
  await page.goto("/settings/models");
  await submitKey(page, "sk-or-reject-replacement");
  await expect(page.getByRole("status")).toContainText(
    "previous key is unchanged",
  );
  const after = await status(page);
  expect(after.source).toBe("app");
  expect(after.credential_version).toBe(1);
  const stale = await page.request.put(CREDENTIAL, {
    headers: await csrf(page),
    data: { draft_key: "sk-or-valid-stale-write", expected_version: 0 },
  });
  expect(stale.status()).toBe(409);
  const text = await stale.text();
  expect(text).not.toContain("sk-or-valid-stale-write");
  expect(JSON.parse(text).code).toBe("stale_version");
  expect((await status(page)).credential_version).toBe(1);
  const removed = await page.request.delete(CREDENTIAL, {
    headers: await csrf(page),
    data: { expected_version: 0 },
  });
  expect(removed.status()).toBe(409);
  expect((await status(page)).source).toBe("app");
});

test("a catalog outage does not undo an authentication-valid save, and is shown separately", async ({
  page,
}) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
  await page.goto("/settings/models");
  await page.evaluate(() => undefined);
  const { writeFileSync, rmSync } = await import("node:fs");
  writeFileSync(CATALOG_DOWN, "");
  try {
    await submitKey(page, "sk-or-valid-during-outage");
    await expect(page.locator('[data-field="auth"]')).toHaveText(
      "The key authenticated.",
    );
    await expect(page.locator('[data-field="catalog"]')).toContainText(
      "Unavailable",
    );
    await expect(page.locator('[data-field="version"]')).toHaveText("2");
    const models = await (await page.request.get("/api/models")).json();
    expect(models.catalog_status).toBe("unavailable");
    expect(
      models.models.every((model: { available: boolean }) => !model.available),
    ).toBe(true);
  } finally {
    rmSync(CATALOG_DOWN);
  }
  await page.reload();
  await expect(page.locator('[data-field="catalog"]')).toHaveText("Available");
  const models = await (await page.request.get("/api/models")).json();
  expect(
    models.models.map((model: { profile: string }) => model.profile).sort(),
  ).toEqual(["openrouter_astra", "openrouter_deepseek_flash"]);
  expect(
    models.models.every((model: { available: boolean }) => model.available),
  ).toBe(true);
  expect(JSON.stringify(models)).not.toContain("sk-or");
});

test("Validate and Disconnect work, and disconnecting blocks model work again", async ({
  page,
}) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
  await page.goto("/settings/models");
  await page.getByRole("button", { name: "Validate", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("Saved.");
  await page.getByRole("button", { name: "Disconnect" }).click();
  await expect(page.locator('[data-field="source"]')).toHaveText("None");
  await page.goto("/");
  await page.getByRole("textbox", { name: "Goal" }).fill(DRAFT);
  await page.getByRole("button", { name: "Run" }).click();
  await expect(
    page.locator('[data-outcome="credentials_required"]'),
  ).toBeVisible();
  await page.goto("/settings/models");
  await submitKey(page, VALID);
  await expect(page.locator('[data-field="auth"]')).toHaveText(
    "The key authenticated.",
  );
});

test("an environment-managed key shows no field, cannot be replaced or removed, and stays read-only", async ({
  page,
}) => {
  await signIn(page, EMAIL_B, PASSWORD_B);
  await page.goto("/settings/models");
  await expect(page.locator('[data-field="source"]')).toContainText(
    "server environment",
  );
  await expect(page.getByLabel(/API key|Replace key/)).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Disconnect" })).toHaveCount(0);
  const before = await status(page);
  const refused = await page.request.put(CREDENTIAL, {
    headers: await csrf(page),
    data: {
      draft_key: "sk-or-valid-over-environment",
      expected_version: before.settings_version,
    },
  });
  expect(refused.status()).toBe(409);
  expect((await refused.json()).code).toBe("environment_managed");
  expect(JSON.stringify(await status(page))).not.toContain("sk-or");
  await page.screenshot({
    path: `${process.env.AUTOBOTS_WEB_SCREENSHOTS}/models-environment.png`,
    fullPage: true,
  });
});

test("only an owner can change settings, and a workspace header cannot cross workspaces", async ({
  page,
}) => {
  await signIn(page, EMAIL_C, PASSWORD_C);
  const header = { "X-Autobots-Workspace": WORKSPACE_A };
  const readable = await page.request.get("/api/settings/model-providers", {
    headers: header,
  });
  expect(readable.status()).toBe(200);
  const refused = await page.request.put(CREDENTIAL, {
    headers: { ...(await csrf(page)), ...header },
    data: { draft_key: "sk-or-valid-not-an-owner", expected_version: 0 },
  });
  expect(refused.status()).toBe(403);
  expect((await refused.json()).code).toBe("owner_required");
  const policy = await page.request.put("/api/settings/model-policy", {
    headers: { ...(await csrf(page)), ...header },
    data: {
      expected_version: 0,
      default_profile: "openrouter_astra",
      role_overrides: {},
    },
  });
  expect(policy.status()).toBe(403);
});

test("a workspace outside the session's memberships is refused", async ({
  page,
}) => {
  await signIn(page, EMAIL_B, PASSWORD_B);
  const refused = await page.request.get("/api/settings/model-providers", {
    headers: { "X-Autobots-Workspace": WORKSPACE_A },
  });
  expect(refused.status()).toBe(403);
});

test("the model policy is versioned, and refuses an unapproved value", async ({
  page,
}) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
  const headers = await csrf(page);
  const saved = await page.request.put("/api/settings/model-policy", {
    headers,
    data: {
      expected_version: 0,
      default_profile: "openrouter_astra",
      role_overrides: { coder: "openrouter_deepseek_flash" },
    },
  });
  expect(saved.status()).toBe(200);
  const state = await saved.json();
  expect(state.version).toBe(1);
  const coder = state.policy.bindings.find(
    (binding: { role: string }) => binding.role === "coder",
  );
  expect(coder.profile).toBe("openrouter_deepseek_flash");
  expect(
    state.policy.bindings.filter(
      (binding: { profile: string }) => binding.profile === "openrouter_astra",
    ),
  ).toHaveLength(13);
  const stale = await page.request.put("/api/settings/model-policy", {
    headers,
    data: {
      expected_version: 0,
      default_profile: "openrouter_deepseek_flash",
      role_overrides: {},
    },
  });
  expect(stale.status()).toBe(409);
  const unknown = await page.request.put("/api/settings/model-policy", {
    headers,
    data: {
      expected_version: 1,
      default_profile: "openai/gpt-6-astra",
      role_overrides: {},
    },
  });
  expect(unknown.status()).toBe(422);
});

test("no secret ever appears in these logs", () => {
  const log = readFileSync(
    process.env.AUTOBOTS_TEST_UPSTREAM_LOG ?? "",
    "utf8",
  );
  expect(log).not.toContain("sk-or");
});
