import { readFileSync } from "node:fs";

import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// US-14.17 and Decision 0024 against the disposable identity stack, run by scripts/qualify_identity.py.
// That stack's configuration root has a Jina key in its .env, and no Tavily key anywhere.

const EMAIL_A = process.env.AUTOBOTS_TEST_OWNER_EMAIL ?? "";
const PASSWORD_A = process.env.AUTOBOTS_TEST_OWNER_PASSWORD ?? "";
// A member of workspace A only, who isn't its owner.
const EMAIL_READER = process.env.AUTOBOTS_TEST_READER_EMAIL ?? "";
const PASSWORD_READER = process.env.AUTOBOTS_TEST_READER_PASSWORD ?? "";
const CONFIG_DOTENV = process.env.AUTOBOTS_TEST_CONFIG_DOTENV ?? "";
const TAVILY = "tvly-fixtureSavedInSettings0001";
const JINA = "jina_fixtureSavedInSettings0001";
const ENV_JINA = "jina_fixtureConfigRoot0001";

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

type Key = { provider: string; source: string | null; version: number };

async function keys(page: Page): Promise<Key[]> {
  const reply = await page.request.get("/api/settings/tool-keys");
  expect(reply.status()).toBe(200);
  const text = await reply.text();
  for (const secret of [TAVILY, JINA, ENV_JINA]) {
    expect(text).not.toContain(secret);
  }
  return (JSON.parse(text) as { keys: Key[] }).keys;
}

async function version(page: Page, provider: string): Promise<number> {
  return (await keys(page)).find((key) => key.provider === provider)!.version;
}

function card(page: Page, provider: string) {
  return page.locator(`[data-provider="${provider}"]`);
}

test("the owner saves and removes tool keys, and a saved key wins over .env", async ({
  page,
}) => {
  const dotenvBefore = readFileSync(CONFIG_DOTENV);
  await signIn(page, EMAIL_A, PASSWORD_A);
  await page.goto("/settings/tool-keys");
  await expect(page.getByRole("heading", { name: "Tool keys" })).toBeVisible();
  await expect(
    card(page, "tavily").locator('[data-field="source"]'),
  ).toHaveText("None. Its tools are unavailable");
  await expect(card(page, "jina").locator('[data-field="source"]')).toHaveText(
    "JINA_API_KEY from the server environment or .env",
  );
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(
    results.violations.map((item) => `${item.id}: ${item.nodes.length}`),
  ).toEqual([]);

  // TS-03: the repair names Settings and .env, and an environment key says where it comes from.
  await page.goto("/tools");
  const tavily = page.locator('[data-tool="tavily_search"]');
  await expect(tavily).toContainText("Unavailable: key not set");
  await expect(tavily.locator('[data-field="repair"]')).toHaveText(
    "Save a Tavily key in Settings → Tool keys, or set TAVILY_API_KEY in .env, then restart the worker and the API.",
  );
  await expect(page.locator('[data-tool="search_web"]')).toContainText(
    "Key from the environment",
  );

  // A malformed value and a stale version leave nothing saved, and call no provider.
  const malformed = await page.request.put("/api/settings/tool-keys/tavily", {
    headers: await csrf(page),
    data: { draft_key: "short", expected_version: 0 },
  });
  expect(malformed.status()).toBe(422);
  const stale = await page.request.put("/api/settings/tool-keys/tavily", {
    headers: await csrf(page),
    data: { draft_key: TAVILY, expected_version: 7 },
  });
  expect(stale.status()).toBe(409);
  expect((await stale.json()).code).toBe("stale_version");

  // Save through the form: the field is cleared, and the source becomes Settings.
  await page.goto("/settings/tool-keys");
  const field = card(page, "tavily").getByLabel("API key");
  await field.fill(TAVILY);
  await card(page, "tavily").getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("status")).toHaveText("Saved.");
  await expect(card(page, "tavily").getByLabel("Replace key")).toHaveValue("");
  await expect(
    card(page, "tavily").locator('[data-field="source"]'),
  ).toHaveText("Saved here for this workspace, encrypted on this Mac");
  expect(await page.content()).not.toContain(TAVILY);

  await page.goto("/tools");
  await expect(page.locator('[data-tool="tavily_search"]')).toContainText(
    "Key from Settings",
  );
  const catalog = await page.request.get("/api/v1/tools");
  expect(await catalog.text()).not.toContain(TAVILY);

  // A saved Jina key wins over the .env one, and removing it falls back to .env.
  const saved = await page.request.put("/api/settings/tool-keys/jina", {
    headers: await csrf(page),
    data: { draft_key: JINA, expected_version: await version(page, "jina") },
  });
  expect(saved.status()).toBe(200);
  expect(await saved.text()).not.toContain(JINA);
  expect(
    (await keys(page)).find((key) => key.provider === "jina")!.source,
  ).toBe("settings");
  await page.goto("/settings/tool-keys");
  await card(page, "jina").getByRole("button", { name: "Remove" }).click();
  await expect(page.getByRole("status")).toHaveText("Removed.");
  await expect(card(page, "jina").locator('[data-field="source"]')).toHaveText(
    "JINA_API_KEY from the server environment or .env",
  );
  expect(readFileSync(CONFIG_DOTENV).equals(dotenvBefore)).toBe(true);

  await card(page, "tavily").getByRole("button", { name: "Remove" }).click();
  await expect(
    card(page, "tavily").locator('[data-field="source"]'),
  ).toHaveText("None. Its tools are unavailable");
});

test("a member sees each key's source and can't change a key", async ({
  page,
}) => {
  await signIn(page, EMAIL_READER, PASSWORD_READER);
  await page.goto("/settings/tool-keys");
  await expect(
    card(page, "jina").locator('[data-field="source"]'),
  ).toBeVisible();
  const listed = await keys(page);
  expect(listed.map((key) => key.provider)).toEqual(["tavily", "jina"]);
  for (const method of ["put", "delete"] as const) {
    const refused = await page.request[method](
      "/api/settings/tool-keys/tavily",
      {
        headers: await csrf(page),
        data:
          method === "put"
            ? { draft_key: TAVILY, expected_version: 0 }
            : { expected_version: 0 },
      },
    );
    expect(refused.status()).toBe(403);
    expect((await refused.json()).code).toBe("owner_required");
  }
});
