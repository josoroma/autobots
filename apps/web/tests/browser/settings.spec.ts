import { readFileSync, rmSync, writeFileSync } from "node:fs";

import {
  parseExpertList,
  parseExpertView,
  parseModelList,
  parseModelPolicyState,
} from "@autobots/api-client";
import type { Page } from "@playwright/test";

import {
  csrfHeaders,
  expectRefusal,
  getJson,
  send,
  writeHeaders,
} from "./support/api.ts";
import { signIn, users } from "./support/auth.ts";
import { arranged, need, screenshotPath } from "./support/env.ts";
import { expect, test } from "./support/fixtures.ts";
import {
  providerMessage,
  submitProviderKey,
  VALID_PROVIDER_KEY as VALID,
} from "./support/keys.ts";
import { captureBodies } from "./support/leaks.ts";
import { providerStatus, startsWithoutProviderKey } from "./support/state.ts";

const stack = arranged({
  workspaceA: "AUTOBOTS_TEST_WORKSPACE_A",
  catalogDown: "AUTOBOTS_TEST_CATALOG_DOWN",
});
const CREDENTIAL = "/api/settings/model-providers/openrouter/credential";
const DRAFT = "Summarize the quarterly notes";

const models = (page: Page) =>
  getJson(page, { path: "/api/models", parse: parseModelList });

// Workspace A has no saved key when these start, as they read. runs.spec.ts removes the one the main
// project's earlier suites save. The check is scoped here so a worker restarted after a failure
// below doesn't repeat it for the tests that don't need it (TWEB-01).
test.describe(() => {
  startsWithoutProviderKey("runs.spec.ts removes workspace A's key");

  test("without a key, local work stays usable and a model call is credentials_required, with the draft kept", async ({
    page,
  }) => {
    await signIn(page, users.owner);
    await page.getByRole("textbox", { name: "Goal" }).fill(DRAFT);
    const intents: string[] = [];
    page.on("request", (request) => {
      if (request.url().endsWith("/api/v1/runs"))
        intents.push(request.method());
    });
    await page.getByRole("button", { name: "Run", exact: true }).click();
    await expect(
      page.locator('[data-outcome="credentials_required"]'),
    ).toBeVisible();
    expect(intents).toEqual(["POST"]);
    await expect(page.getByRole("textbox", { name: "Goal" })).toHaveValue(
      DRAFT,
    );
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
      path: screenshotPath("models-missing.png"),
      fullPage: true,
    });
  });

  test("a rejected or uncheckable draft changes nothing and does not say more than it should", async ({
    page,
  }) => {
    await signIn(page, users.owner);
    await page.goto("/settings/models");
    await submitProviderKey(page, "sk-or-reject-arranged");
    await expect(await providerMessage(page)).toContainText("was not accepted");
    await expect(page.getByLabel("API key")).toHaveValue("");
    expect((await providerStatus(page)).source).toBe("none");
    await submitProviderKey(page, "sk-or-down-arranged");
    await expect(await providerMessage(page)).toContainText(
      "could not be checked",
    );
    expect((await providerStatus(page)).source).toBe("none");
  });
});

// Each test here builds on the key the one before saved: version 1, kept through a bad replacement,
// version 2 during an outage, then validated, disconnected and saved again. Serial, so when one fails
// the rest are skipped rather than failing for its reason (TWEB-07).
test.describe(() => {
  test.describe.configure({ mode: "serial" });
  startsWithoutProviderKey("the tests above save no key");

  test("Save and validate encrypts, keeps statuses separate, returns to the draft and starts nothing", async ({
    page,
  }) => {
    await signIn(page, users.owner);
    await page.getByRole("textbox", { name: "Goal" }).fill(DRAFT);
    await page.goto("/settings/models");
    const bodies = captureBodies(page);
    const requests: string[] = [];
    page.on("request", (request) => requests.push(request.url()));
    await submitProviderKey(page, VALID);
    await expect(page.locator('[data-field="auth"]')).toHaveText(
      "The key authenticated.",
    );
    await expect(page.getByLabel("Replace key")).toHaveValue("");
    await expect(page.locator('[data-field="source"]')).toContainText(
      "encrypted",
    );
    await expect(page.locator('[data-field="catalog"]')).toHaveText(
      "Available",
    );
    await expect(page.locator('[data-field="qualification"]')).toContainText(
      "A configured key does not mean a route was tested",
    );
    await expect(page.locator('[data-field="version"]')).toHaveText("1");
    // Every body read so far, the save's own reply among them.
    const read = await bodies();
    expect(
      read.some(
        (reply) => reply.method === "PUT" && reply.url.endsWith(CREDENTIAL),
      ),
      "the credential save's reply was read",
    ).toBe(true);
    for (const reply of read)
      expect(reply.body, reply.url).not.toContain(VALID);
    const stored = await page.evaluate(() =>
      JSON.stringify({
        ...localStorage,
        ...sessionStorage,
        cookie: document.cookie,
      }),
    );
    expect(stored).not.toContain(VALID);
    await page.screenshot({
      path: screenshotPath("models-configured.png"),
      fullPage: true,
    });
    await page.getByRole("link", { name: "Return to your draft" }).click();
    await expect(page.getByRole("textbox", { name: "Goal" })).toHaveValue(
      DRAFT,
    );
    // A negative observation: returning to the draft starts no run within 300 ms.
    await page.waitForTimeout(300);
    expect(requests.filter((url) => url.includes("/runs/"))).toEqual([]);
  });

  test("a bad replacement keeps the prior key, and a stale write is a conflict with no secret", async ({
    page,
  }) => {
    await signIn(page, users.owner);
    await page.goto("/settings/models");
    await submitProviderKey(page, "sk-or-reject-replacement");
    await expect(await providerMessage(page)).toContainText(
      "previous key is unchanged",
    );
    const after = await providerStatus(page);
    expect(after.source).toBe("app");
    expect(after.credential_version).toBe(1);
    const stale = await page.request.put(CREDENTIAL, {
      headers: await csrfHeaders(page),
      data: { draft_key: "sk-or-valid-stale-write", expected_version: 0 },
    });
    expect(await stale.text()).not.toContain("sk-or-valid-stale-write");
    await expectRefusal(stale, { status: 409, code: "stale_version" });
    expect((await providerStatus(page)).credential_version).toBe(1);
    const removed = await page.request.delete(CREDENTIAL, {
      headers: await csrfHeaders(page),
      data: { expected_version: 0 },
    });
    expect(removed.status()).toBe(409);
    expect((await providerStatus(page)).source).toBe("app");
  });

  test("a catalog outage does not undo an authentication-valid save, and is shown separately", async ({
    page,
  }) => {
    await signIn(page, users.owner);
    await page.goto("/settings/models");
    writeFileSync(stack.catalogDown, "");
    try {
      await submitProviderKey(page, "sk-or-valid-during-outage");
      await expect(page.locator('[data-field="auth"]')).toHaveText(
        "The key authenticated.",
      );
      await expect(page.locator('[data-field="catalog"]')).toContainText(
        "Unavailable",
      );
      await expect(page.locator('[data-field="version"]')).toHaveText("2");
      const during = await models(page);
      expect(during.catalog_status).toBe("unavailable");
      expect(during.models.every((model) => !model.available)).toBe(true);
    } finally {
      rmSync(stack.catalogDown);
    }
    await page.reload();
    await expect(page.locator('[data-field="catalog"]')).toHaveText(
      "Available",
    );
    const after = await models(page);
    expect(after.models.map((model) => model.profile).sort()).toEqual([
      "openrouter_deepseek_flash",
      "openrouter_sol",
      "openrouter_terra",
    ]);
    // US-14.15: Sol is approved, listed and, its route qualified, offered.
    await expect(
      page.locator('[data-approved-model="openrouter_sol"]'),
    ).toContainText("gpt-6.1-sol");
    await expect(
      page.locator('[data-approved-model="openrouter_sol"]'),
    ).not.toContainText("not offered");
    expect(after.models.every((model) => model.available)).toBe(true);
    expect(JSON.stringify(after)).not.toContain("sk-or");
  });

  test("Validate and Disconnect work, and disconnecting blocks model work again", async ({
    page,
  }) => {
    await signIn(page, users.owner);
    await page.goto("/settings/models");
    await page.getByRole("button", { name: "Validate", exact: true }).click();
    // R-19: Validate says it checked, not that it saved.
    await expect(await providerMessage(page)).toHaveText(
      "Checked. The key's status above is current.",
    );
    await page.getByRole("button", { name: "Disconnect" }).click();
    await expect(page.locator('[data-field="source"]')).toHaveText("None");
    await page.goto("/");
    await page.getByRole("textbox", { name: "Goal" }).fill(DRAFT);
    await page.getByRole("button", { name: "Run", exact: true }).click();
    await expect(
      page.locator('[data-outcome="credentials_required"]'),
    ).toBeVisible();
    await page.goto("/settings/models");
    await submitProviderKey(page, VALID);
    await expect(page.locator('[data-field="auth"]')).toHaveText(
      "The key authenticated.",
    );
  });
});

test("an environment-managed key shows no field, cannot be replaced or removed, and stays read-only", async ({
  page,
}) => {
  await signIn(page, users.ownerB);
  await page.goto("/settings/models");
  await expect(page.locator('[data-field="source"]')).toContainText(
    "server environment",
  );
  await expect(page.getByLabel(/API key|Replace key/)).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Disconnect" })).toHaveCount(0);
  const before = await providerStatus(page);
  const refused = await page.request.put(CREDENTIAL, {
    headers: await csrfHeaders(page),
    data: {
      draft_key: "sk-or-valid-over-environment",
      expected_version: before.settings_version,
    },
  });
  await expectRefusal(refused, { status: 409, code: "environment_managed" });
  expect(JSON.stringify(await providerStatus(page))).not.toContain("sk-or");
  await page.screenshot({
    path: screenshotPath("models-environment.png"),
    fullPage: true,
  });
});

test("only an owner can change settings, and a workspace header cannot cross workspaces", async ({
  page,
}) => {
  await signIn(page, users.member);
  const header = { "X-Autobots-Workspace": stack.workspaceA };
  const readable = await page.request.get("/api/settings/model-providers", {
    headers: header,
  });
  expect(readable.status()).toBe(200);
  const refused = await page.request.put(CREDENTIAL, {
    headers: { ...(await csrfHeaders(page)), ...header },
    data: { draft_key: "sk-or-valid-not-an-owner", expected_version: 0 },
  });
  await expectRefusal(refused, { status: 403, code: "owner_required" });
  const policy = await page.request.put("/api/settings/model-policy", {
    headers: { ...(await csrfHeaders(page)), ...header },
    data: {
      expected_version: 0,
      default_profile: "openrouter_terra",
      role_overrides: {},
    },
  });
  expect(policy.status()).toBe(403);
});

test("a workspace outside the session's memberships is refused", async ({
  page,
}) => {
  await signIn(page, users.ownerB);
  const refused = await page.request.get("/api/settings/model-providers", {
    headers: { "X-Autobots-Workspace": stack.workspaceA },
  });
  expect(refused.status()).toBe(403);
});

test("the model policy is versioned, and refuses an unapproved value", async ({
  page,
}) => {
  await signIn(page, users.owner);
  const POLICY = "/api/settings/model-policy";
  const headers = await csrfHeaders(page);
  await test.step("the first save is version 1", async () => {
    const state = await send(page, {
      method: "PUT",
      path: POLICY,
      key: null,
      data: {
        expected_version: 0,
        default_profile: "openrouter_terra",
        role_overrides: { coder: "openrouter_terra" },
      },
      status: 200,
      parse: parseModelPolicyState,
    });
    expect(state.version).toBe(1);
    expect(
      state.policy.bindings.find((item) => item.role === "coder")?.profile,
    ).toBe("openrouter_terra");
  });
  await test.step("naming DeepSeek in the policy changes nothing", async () => {
    // Named on a write, DeepSeek is refused with why, and nothing stored changes.
    for (const data of [
      {
        expected_version: 1,
        default_profile: "openrouter_deepseek_flash",
        role_overrides: {},
      },
      {
        expected_version: 1,
        default_profile: "openrouter_terra",
        role_overrides: { coder: "openrouter_deepseek_flash" },
      },
    ]) {
      const refusal = await expectRefusal(
        await page.request.put(POLICY, { headers, data }),
        { status: 422, code: "model_not_offered" },
      );
      expect(refusal.message).toContain("isn't offered for new runs");
    }
    const kept = await getJson(page, {
      path: POLICY,
      parse: parseModelPolicyState,
    });
    expect(kept.version).toBe(1);
  });
  await test.step("a run or an Expert naming DeepSeek is refused", async () => {
    const namedRun = await page.request.post("/api/v1/runs", {
      headers: await writeHeaders(page, `named-${Date.now()}`),
      data: { goal_text: "names it", run_profile: "openrouter_deepseek_flash" },
    });
    await expectRefusal(namedRun, { status: 422, code: "model_not_offered" });
    const expert = await page.request.post("/api/v1/experts", {
      headers: await writeHeaders(page, `expert-${Date.now()}`),
      data: {
        name: "Names DeepSeek",
        config: { role_bindings: { executor: "openrouter_deepseek_flash" } },
      },
    });
    await expectRefusal(expert, { status: 422, code: "model_not_offered" });
    const experts = await getJson(page, {
      path: "/api/v1/experts",
      parse: parseExpertList,
    });
    expect(
      experts.experts.filter((item) => item.name === "Names DeepSeek"),
    ).toEqual([]);
    const created = await send(page, {
      path: "/api/v1/experts",
      key: `plain-${Date.now()}`,
      data: { name: `Plain ${Date.now()}`, config: {} },
      status: 201,
      parse: parseExpertView,
    });
    const revision = await page.request.post(
      `/api/v1/experts/${created.id}/versions`,
      {
        headers: await writeHeaders(page, `revision-${Date.now()}`),
        data: {
          expected_version: created.latest_version,
          config: { role_bindings: { executor: "openrouter_deepseek_flash" } },
        },
      },
    );
    await expectRefusal(revision, { status: 422, code: "model_not_offered" });
  });
  await test.step("a stale or unknown write is refused", async () => {
    const stale = await page.request.put(POLICY, {
      headers,
      data: {
        expected_version: 0,
        default_profile: "openrouter_terra",
        role_overrides: {},
      },
    });
    expect(stale.status()).toBe(409);
    const unknown = await page.request.put(POLICY, {
      headers,
      data: {
        expected_version: 1,
        default_profile: "openai/gpt-6.1-terra",
        role_overrides: {},
      },
    });
    expect(unknown.status()).toBe(422);
  });
});

test("no secret ever appears in these logs", () => {
  const log = readFileSync(need("AUTOBOTS_TEST_UPSTREAM_LOG"), "utf8");
  expect(log).not.toContain("sk-or");
});
