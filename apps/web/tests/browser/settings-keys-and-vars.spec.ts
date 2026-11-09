import { readFileSync } from "node:fs";

import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// US-14.17 and US-14.18, Decisions 0024 and 0025, against the disposable identity stack run by
// scripts/qualify_identity.py. That stack's configuration root has a Jina key in its .env, and no
// other key, repository or browsing switch anywhere. Every value below is a fixture, and each test
// removes what it saved, since later suites expect no key.

const EMAIL_A = process.env.AUTOBOTS_TEST_OWNER_EMAIL ?? "";
const PASSWORD_A = process.env.AUTOBOTS_TEST_OWNER_PASSWORD ?? "";
// A member of workspace A only, who isn't its owner.
const EMAIL_READER = process.env.AUTOBOTS_TEST_READER_EMAIL ?? "";
const PASSWORD_READER = process.env.AUTOBOTS_TEST_READER_PASSWORD ?? "";
const CONFIG_DOTENV = process.env.AUTOBOTS_TEST_CONFIG_DOTENV ?? "";
const TAVILY = "tvly-fixtureSavedInSettings0001";
const JINA = "jina_fixtureSavedInSettings0001";
const GITHUB = "github_pat_fixtureSavedInSettings0001";
const ENV_JINA = "jina_fixtureConfigRoot0001";
const SECRETS = [TAVILY, JINA, GITHUB, ENV_JINA];
const ROUTE = "/api/settings/keys-and-vars";

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

type Item = {
  name: string;
  kind: string;
  source: string | null;
  value: string | null;
  version: number;
};

async function items(page: Page): Promise<Item[]> {
  const reply = await page.request.get(ROUTE);
  expect(reply.status()).toBe(200);
  const text = await reply.text();
  for (const secret of SECRETS) expect(text).not.toContain(secret);
  return (JSON.parse(text) as { items: Item[] }).items;
}

async function item(page: Page, name: string): Promise<Item> {
  return (await items(page)).find((entry) => entry.name === name)!;
}

async function put(page: Page, name: string, value: string, version?: number) {
  return page.request.put(`${ROUTE}/${name}`, {
    headers: await csrf(page),
    data: {
      value,
      expected_version: version ?? (await item(page, name)).version,
    },
  });
}

async function remove(page: Page, name: string) {
  return page.request.delete(`${ROUTE}/${name}`, {
    headers: await csrf(page),
    data: { expected_version: (await item(page, name)).version },
  });
}

function card(page: Page, name: string) {
  return page.locator(`[data-item="${name}"]`);
}

test("Keys & vars replaces Tool keys, and the owner saves and removes keys and values", async ({
  page,
}) => {
  const dotenvBefore = readFileSync(CONFIG_DOTENV);
  await signIn(page, EMAIL_A, PASSWORD_A);

  // The former page and routes are gone.
  expect((await page.goto("/settings/tool-keys"))?.status()).toBe(404);
  expect((await page.request.get("/api/settings/tool-keys")).status()).toBe(
    404,
  );

  await page.goto("/settings");
  await page.getByRole("link", { name: "Keys & vars", exact: true }).click();
  await expect(page).toHaveURL(/\/settings\/keys-and-vars$/);
  await expect(
    page.getByRole("heading", { name: "Keys & vars" }),
  ).toBeVisible();
  const listed = await items(page);
  expect(listed.map((entry) => [entry.name, entry.kind])).toEqual([
    ["tavily", "secret"],
    ["jina", "secret"],
    ["github_token", "secret"],
    ["github_repository", "value"],
    ["browser_executor", "value"],
  ]);
  await expect(
    card(page, "tavily").locator('[data-field="source"]'),
  ).toHaveText("None. Its tools are unavailable");
  await expect(card(page, "jina").locator('[data-field="source"]')).toHaveText(
    "JINA_API_KEY from the server environment or .env",
  );
  await expect(
    card(page, "github_repository").locator('[data-field="source"]'),
  ).toHaveText("None. GITHUB_REPOSITORY isn't set");
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(
    results.violations.map((entry) => `${entry.id}: ${entry.nodes.length}`),
  ).toEqual([]);

  // TS-03: the repair names Keys & vars and .env, and an environment key says where it comes from.
  await page.goto("/tools");
  const tavily = page.locator('[data-tool="tavily_search"]');
  await expect(tavily).toContainText("Unavailable: key not set");
  await expect(tavily.locator('[data-field="repair"]')).toHaveText(
    "Save a Tavily key in Settings → Keys & vars, or set TAVILY_API_KEY in .env, then restart the worker and the API.",
  );
  await expect(page.locator('[data-tool="search_web"]')).toContainText(
    "Key from the environment",
  );

  // Each check refuses, changes nothing, and calls no provider.
  for (const [name, value, code] of [
    ["tavily", "short", "invalid_key"],
    ["github_token", "has a space", "invalid_key"],
    ["github_repository", "not a repository", "invalid_value"],
    ["github_repository", "https://evil.example/owner/repo", "invalid_value"],
    ["browser_executor", "on", "invalid_value"],
  ] as const) {
    const refused = await put(page, name, value);
    expect(refused.status(), `${name} ${value}`).toBe(422);
    expect((await refused.json()).code).toBe(code);
  }
  const stale = await put(page, "tavily", TAVILY, 7);
  expect(stale.status()).toBe(409);
  expect((await stale.json()).code).toBe("stale_version");
  expect((await item(page, "tavily")).source).toBeNull();

  // Save through the form: a secret's field is cleared, and its source becomes Settings.
  await page.goto("/settings/keys-and-vars");
  await card(page, "tavily").getByLabel("API key").fill(TAVILY);
  await card(page, "tavily").getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("status")).toHaveText("Saved.");
  await expect(card(page, "tavily").getByLabel("Replace key")).toHaveValue("");
  await expect(
    card(page, "tavily").locator('[data-field="source"]'),
  ).toHaveText("Saved here for this workspace, encrypted on this Mac");
  await card(page, "github_repository")
    .getByLabel("Set for this workspace")
    .fill("owner/throwaway");
  await card(page, "github_repository")
    .getByRole("button", { name: "Save" })
    .click();
  await expect(
    card(page, "github_repository").locator('[data-field="value"]'),
  ).toHaveText("owner/throwaway");
  await card(page, "browser_executor")
    .getByLabel("Set for this workspace")
    .selectOption("disabled");
  await card(page, "browser_executor")
    .getByRole("button", { name: "Save" })
    .click();
  await expect(
    card(page, "browser_executor").locator('[data-field="value"]'),
  ).toHaveText("disabled");
  expect((await put(page, "github_token", GITHUB)).status()).toBe(200);
  expect(await page.content()).not.toContain(TAVILY);

  // With a saved token and repository, the GitHub tools become available from Settings.
  await page.goto("/tools");
  await expect(page.locator('[data-tool="tavily_search"]')).toContainText(
    "Key from Settings",
  );
  await expect(page.locator('[data-tool="github_read_file"]')).toContainText(
    "Key from Settings",
  );
  await expect(page.locator('[data-tool="browse_goal"]')).toContainText(
    "Unavailable: disabled by policy",
  );
  const catalog = await page.request.get("/api/v1/tools");
  const text = await catalog.text();
  for (const secret of SECRETS) expect(text).not.toContain(secret);

  // A saved Jina key wins over the .env one, and removing it falls back to .env.
  expect((await put(page, "jina", JINA)).status()).toBe(200);
  expect((await item(page, "jina")).source).toBe("settings");
  await page.goto("/settings/keys-and-vars");
  await card(page, "jina").getByRole("button", { name: "Remove" }).click();
  await expect(page.getByRole("status")).toHaveText("Removed.");
  await expect(card(page, "jina").locator('[data-field="source"]')).toHaveText(
    "JINA_API_KEY from the server environment or .env",
  );
  expect(readFileSync(CONFIG_DOTENV).equals(dotenvBefore)).toBe(true);

  for (const name of [
    "tavily",
    "github_token",
    "github_repository",
    "browser_executor",
  ]) {
    expect((await remove(page, name)).status(), name).toBe(200);
  }
  const after = await items(page);
  expect(after.filter((entry) => entry.source === "settings")).toEqual([]);
  expect(
    after.find((entry) => entry.name === "github_repository")?.value,
  ).toBeNull();
});

test("a member sees each source and the values, never a secret, and can't change one", async ({
  browser,
}) => {
  const owner = await (await browser.newContext()).newPage();
  await signIn(owner, EMAIL_A, PASSWORD_A);
  expect(
    (await put(owner, "github_repository", "owner/visible")).status(),
  ).toBe(200);
  expect((await put(owner, "github_token", GITHUB)).status()).toBe(200);

  const page = await (await browser.newContext()).newPage();
  await signIn(page, EMAIL_READER, PASSWORD_READER);
  await page.goto("/settings/keys-and-vars");
  await expect(
    card(page, "github_repository").locator('[data-field="value"]'),
  ).toHaveText("owner/visible");
  const token = await item(page, "github_token");
  expect([token.source, token.value]).toEqual(["settings", null]);
  for (const name of [
    "tavily",
    "github_token",
    "github_repository",
    "browser_executor",
  ]) {
    for (const method of ["put", "delete"] as const) {
      const refused = await page.request[method](`${ROUTE}/${name}`, {
        headers: await csrf(page),
        data:
          method === "put"
            ? { value: "owner/other", expected_version: 0 }
            : { expected_version: 0 },
      });
      expect(refused.status(), `${method} ${name}`).toBe(403);
      expect((await refused.json()).code).toBe("owner_required");
    }
  }

  expect((await remove(owner, "github_repository")).status()).toBe(200);
  expect((await remove(owner, "github_token")).status()).toBe(200);
});
