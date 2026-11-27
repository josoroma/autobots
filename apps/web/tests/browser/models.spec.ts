import {
  parseModelList,
  parseModelPolicyState,
  parseModelSourceState,
  type ModelPolicyState,
} from "@autobots/api-client";
import type { Page } from "@playwright/test";

import { expectNoA11yViolations } from "./support/a11y.ts";
import { getJson, send } from "./support/api.ts";
import { signIn, users } from "./support/auth.ts";
import { need } from "./support/env.ts";
import { expect, test } from "./support/fixtures.ts";

// US-15.8, PRD-Studio MD-01 to MD-03, against the fixture catalog and an owner arranged by
// scripts/qualify_identity.py: no saved default, a `coder` override, and a run whose Expert
// binds the executor to Sol.
const TERRA = "openrouter_terra";
const SOL = "openrouter_sol";

function source(page: Page, role: string) {
  return page
    .locator(`label[for="role-${role}"]`)
    .locator("xpath=..")
    .locator("[data-binding-source]");
}

function stored(page: Page): Promise<ModelPolicyState> {
  return getJson(page, {
    path: "/api/settings/model-policy",
    parse: parseModelPolicyState,
  });
}

test.describe.configure({ mode: "serial" });

test("each profile shows catalog prices, capabilities and the fetch time, apart from qualification", async ({
  page,
}) => {
  await signIn(page, users.models);
  await page.goto("/settings/models");
  const terra = page.locator(`[data-approved-model="${TERRA}"]`);
  await expect(terra.locator('[data-price="input"]')).toHaveText(
    "US$1.25 per 1M tokens",
  );
  await expect(terra.locator('[data-price="output"]')).toHaveText(
    "US$10.00 per 1M tokens",
  );
  const sol = page.locator(`[data-approved-model="${SOL}"]`);
  await expect(sol.locator('[data-price="input"]')).toHaveText(
    "US$3.00 per 1M tokens",
  );
  await expect(sol.locator('[data-price="output"]')).toHaveText(
    "US$15.00 per 1M tokens",
  );
  await expect(terra).toContainText("Capabilities, from the catalog");
  await expect(terra.locator("[data-capability]")).toHaveText([
    "max_tokens",
    "response_format",
    "tool_choice",
    "tools",
  ]);
  // The capabilities aren't a qualification, which the provider section records.
  await expect(terra.locator('[data-field="catalog-facts"]')).not.toContainText(
    /qualif/i,
  );
  const fetched = page.locator('[data-field="catalog-fetched"]');
  await expect(fetched).toContainText(/^Catalog fetched .+\d{1,2}:\d{2}:\d{2}/);
  await expect(fetched).toContainText(
    "Whether a route is qualified is recorded separately",
  );
  const models = await getJson(page, {
    path: "/api/models",
    parse: parseModelList,
  });
  const reported = models.models.find((model) => model.profile === TERRA);
  expect(reported?.input_per_million_micro_usd).toBe(1_250_000);
  expect(reported?.output_per_million_micro_usd).toBe(10_000_000);
  expect(Date.now() - Date.parse(models.fetched_at ?? "")).toBeLessThan(
    120_000,
  );
  await expectNoA11yViolations(page);
});

// US-23.3, Decision 0041 A13: on OpenRouter, the Model source panel shows what Local would offer,
// above the provider panel and the policy. Migrations 70 and 72 store Bonsai 2.5's and Inkling 2
// Mini's qualifications, and no llama-server answers on the fixture's port.
test("the Model source panel sits above the provider panel and shows each local profile", async ({
  page,
}) => {
  await signIn(page, users.models);
  await page.goto("/settings/models");
  const panel = page.locator('[data-panel="model-source"]');
  await expect(panel).toBeVisible();
  await expect(
    panel.locator('[data-source-choice="openrouter"] input'),
  ).toBeChecked();
  await expect(
    panel.locator('[data-local-profile="local_bonsai_2_5_27b"]'),
  ).toContainText("Qualified 2026-11-27");
  // US-23.8: migration 72 stores Inkling 2 Mini's qualification, so both local profiles are offered.
  await expect(
    panel.locator('[data-local-profile="local_inkling_2_mini"]'),
  ).toContainText("Qualified 2026-11-27");
  await expect(panel.locator('[data-source-field="runtime"]')).toContainText(
    "127.0.0.1:",
  );
  const spend = panel.locator('[data-source-field="spend"]');
  await expect(spend).toContainText("US$0.00 per model call");
  await expect(spend).toContainText(
    "SerpApi, Jina and YouTube still leave the Mac",
  );
  const above = await page.evaluate(() => {
    const source = document.querySelector('[data-panel="model-source"]');
    const provider = document.getElementById("openrouter-heading");
    return source !== null && provider !== null
      ? (source.compareDocumentPosition(provider) &
          Node.DOCUMENT_POSITION_FOLLOWING) !==
          0
      : false;
  });
  expect(above).toBe(true);
  const state = await getJson(page, {
    path: "/api/settings/model-source",
    parse: parseModelSourceState,
  });
  expect(state.source).toBe("openrouter");
  await expectNoA11yViolations(page);
});

test("each role says where its binding comes from, on Models and in the run's role map", async ({
  page,
}) => {
  await signIn(page, users.models);
  await page.goto("/settings/models");
  await expect(page.getByLabel("Workspace default")).toHaveValue("");
  await expect(source(page, "coder")).toHaveAttribute(
    "data-binding-source",
    "workspace_override",
  );
  await expect(source(page, "coder")).toContainText("Workspace override");
  await expect(source(page, "researcher")).toHaveText(
    "Built-in default, openai/gpt-6.1-sol-20260929",
  );
  await expect(source(page, "planner")).toHaveText(
    "Built-in default, openai/gpt-6.1-terra-20261026",
  );
  const policy = await stored(page);
  expect(policy.default_profile).toBeNull();
  expect(policy.role_overrides).toEqual({ coder: TERRA });

  await page.goto(`/runs/${need("AUTOBOTS_TEST_MODELS_RUN")}`);
  const map = page.locator('[data-field="role-map"]');
  const line = (role: string) =>
    map.locator("li").filter({ hasText: new RegExp(`^${role}:`) });
  await expect(line("executor")).toContainText("openai/gpt-6.1-sol-20260929");
  await expect(line("executor")).toContainText("· run override");
  await expect(line("coder")).toContainText("· workspace override");
  await expect(line("researcher")).toContainText("openai/gpt-6.1-sol-20260929");
  await expect(line("researcher")).toContainText("· built-in default");
  await expectNoA11yViolations(page);
});

test("Discard restores the saved form, Reset all clears overrides, and a stale Reset all is refused", async ({
  page,
  openPage,
}) => {
  await signIn(page, users.models);
  await page.goto("/settings/models");
  const summary = page.locator('[data-field="policy-summary"]');
  await expect(summary).toHaveText(
    "13 of 14 roles follow the workspace default",
  );
  // A second saved override, so two exist.
  await page.getByLabel("planner", { exact: true }).selectOption(SOL);
  await page.getByRole("button", { name: "Save policy" }).click();
  await expect(page.locator("[data-policy-message]")).toContainText("Saved.");
  await expect(summary).toHaveText(
    "12 of 14 roles follow the workspace default",
  );
  const saved = await stored(page);
  expect(saved.role_overrides).toEqual({ coder: TERRA, planner: SOL });

  // Unsaved edits, then Discard.
  await page.getByLabel("Workspace default").selectOption(TERRA);
  await page.getByLabel("reviewer", { exact: true }).selectOption(SOL);
  await page.getByLabel("coder", { exact: true }).selectOption("");
  await page.getByRole("button", { name: "Discard" }).click();
  await expect(page.getByLabel("Workspace default")).toHaveValue("");
  await expect(page.getByLabel("reviewer", { exact: true })).toHaveValue("");
  await expect(page.getByLabel("coder", { exact: true })).toHaveValue(TERRA);
  await expect(page.getByLabel("planner", { exact: true })).toHaveValue(SOL);
  await expect(page.getByRole("button", { name: "Discard" })).toBeDisabled();
  expect(await stored(page)).toEqual(saved);

  // A screen loaded before the reset.
  const stale = await openPage();
  await signIn(stale, users.models);
  await stale.goto("/settings/models");
  await expect(stale.locator('[data-field="policy-summary"]')).toHaveText(
    "12 of 14 roles follow the workspace default",
  );

  const reset = page.waitForResponse(
    (reply) =>
      reply.url().endsWith("/api/settings/model-policy/reset") &&
      reply.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Reset all" }).click();
  const sent = await reset;
  expect(sent.request().postDataJSON()).toEqual({
    expected_version: saved.version,
  });
  expect(sent.status()).toBe(200);
  await expect(page.locator("[data-policy-message]")).toContainText(
    "Every role override is cleared.",
  );
  await expect(summary).toHaveText(
    "14 of 14 roles follow the workspace default",
  );
  const cleared = await stored(page);
  expect(cleared).toMatchObject({
    version: saved.version + 1,
    default_profile: null,
    role_overrides: {},
  });

  await stale.getByRole("button", { name: "Reset all" }).click();
  await expect(stale.locator("[data-policy-message]")).toHaveText(
    "This policy changed after you opened it, so nothing was reset. Reload the page and try again.",
  );
  expect(await stored(page)).toEqual(cleared);
  await page.reload();
  await expect(summary).toHaveText(
    "14 of 14 roles follow the workspace default",
  );
  await expectNoA11yViolations(page);
});

// US-23.3, Decision 0041 A13: on Local, the composer says nothing goes to OpenRouter and that tool
// calls still leave the Mac, and Home's model chip reads the local runtime, which isn't running in
// this fixture. The owner switches back, so OpenRouter's saved choices are as they were.
test("on Local the composer, Home and the panel say where model calls go", async ({
  page,
}) => {
  await signIn(page, users.models);
  const before = await stored(page);
  const start = await getJson(page, {
    path: "/api/settings/model-source",
    parse: parseModelSourceState,
  });
  const local = await send(page, {
    method: "PUT",
    path: "/api/settings/model-source",
    data: { expected_version: start.version, source: "local" },
    key: null,
    status: 200,
    parse: parseModelSourceState,
  });
  expect(local.source).toBe("local");
  try {
    await page.goto("/");
    const data = page.locator('[data-disclosure="data"]');
    await expect(data).toContainText("Nothing goes to OpenRouter");
    await expect(data).toContainText(
      "SerpApi, Jina and YouTube still leave the Mac",
    );
    await expect(page.locator('[data-disclosure="model"]')).toContainText(
      "served on this Mac",
    );
    await expect(
      page.getByText("Local model isn't running").first(),
    ).toBeVisible();
    await page.goto("/settings/models");
    await expect(
      page.locator(
        '[data-panel="model-source"] [data-source-choice="local"] input',
      ),
    ).toBeChecked();
  } finally {
    const back = await send(page, {
      method: "PUT",
      path: "/api/settings/model-source",
      data: { expected_version: local.version, source: "openrouter" },
      key: null,
      status: 200,
      parse: parseModelSourceState,
    });
    expect(back.source).toBe("openrouter");
  }
  const after = await stored(page);
  expect([after.default_profile, after.role_overrides]).toEqual([
    before.default_profile,
    before.role_overrides,
  ]);
});
