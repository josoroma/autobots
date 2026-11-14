import {
  parseModelPolicyState,
  parseRunWorkspace,
  type ModelPolicyState,
} from "@autobots/api-client";
import type { Page } from "@playwright/test";

import { expectNoA11yViolations } from "./support/a11y.ts";
import { getJson, send } from "./support/api.ts";
import { signIn, users } from "./support/auth.ts";
import { WorkerScenario } from "./support/builders.ts";
import { expect, test } from "./support/fixtures.ts";
import { ensureProviderKey } from "./support/keys.ts";
import { admitRun, cancelUnlessTerminal } from "./support/runs.ts";

// The model policy on Settings. Its name runs it with the slice suites, after settings.spec's versions.
const TERRA = "openrouter_terra";
const DEEPSEEK = "openrouter_deepseek_flash";
const POLICY = "/api/settings/model-policy";

function storedPolicy(page: Page): Promise<ModelPolicyState> {
  return getJson(page, { path: POLICY, parse: parseModelPolicyState });
}

// The worker's scripted route is Terra, so later suites start from the original policy.
async function restore(page: Page): Promise<void> {
  const current = await storedPolicy(page);
  await send(page, {
    method: "PUT",
    path: POLICY,
    key: null,
    data: {
      expected_version: current.version,
      default_profile: TERRA,
      role_overrides: {},
    },
    status: 200,
    parse: parseModelPolicyState,
  });
}

/** Admits a run the scripted worker fails at once, as it only claims to be done. */
function admit(page: Page, label: string): Promise<string> {
  return admitRun(
    page,
    {
      goal_text: `${WorkerScenario.onlyClaims} ${label}`,
      limit_micro_usd: 1000,
    },
    { key: `${label}-${Date.now()}` },
  );
}

async function frozenExecutor(
  page: Page,
  id: string,
): Promise<string | undefined> {
  const view = await getJson(page, {
    path: `/api/v1/runs/${id}/workspace`,
    parse: parseRunWorkspace,
  });
  return view.role_map.find((binding) => binding.role === "executor")?.profile;
}

const select = (page: Page, role: string) =>
  page.getByLabel(role, { exact: true });

test("an owner saves a default of what is offered, and DeepSeek is listed but not offered", async ({
  page,
}) => {
  test.setTimeout(90_000);
  await signIn(page, users.owner);
  await ensureProviderKey(page);
  await restore(page);
  await page.goto("/");
  const before = await admit(page, "before-the-change");
  expect(await frozenExecutor(page, before)).toBe(TERRA);

  await page.goto("/settings/models");
  await expect(page.locator(`[data-approved-model="${TERRA}"]`)).toContainText(
    "openai/gpt-6.1-terra-20261026 (requested as openai/gpt-6.1-terra)",
  );
  await expect(
    page.locator(`[data-approved-model="${DEEPSEEK}"]`),
  ).toContainText(
    "deepseek/deepseek-v4.1-flash-20261017 (requested as deepseek/deepseek-v4.1-flash-1017)",
  );
  await expect(
    page.locator(`[data-approved-model="${DEEPSEEK}"]`),
  ).toContainText("not offered for new runs until it's qualified");
  // Approved and listed, and not something new work can choose.
  await expect(
    page.getByLabel("Workspace default").locator(`option[value="${DEEPSEEK}"]`),
  ).toHaveCount(0);
  await expect(
    select(page, "coder").locator(`option[value="${DEEPSEEK}"]`),
  ).toHaveCount(0);
  const version = (await storedPolicy(page)).version;
  await page.getByLabel("Workspace default").selectOption(TERRA);
  await page.getByRole("button", { name: "Save policy" }).click();
  await expect(page.locator("[data-policy-message]")).toContainText("Saved.");
  expect((await storedPolicy(page)).version).toBe(version + 1);

  await page.goto("/");
  const after = await admit(page, "after-the-change");
  expect(await frozenExecutor(page, after)).toBe(TERRA);
  expect(await frozenExecutor(page, before)).toBe(TERRA);
  await cancelUnlessTerminal(page, after);
  await cancelUnlessTerminal(page, before);

  await page.goto("/settings/models");
  await expect(page.getByLabel("Workspace default")).toHaveValue(TERRA);
  await expectNoA11yViolations(page);
  await restore(page);
});

test("the screen says only the executor dispatches, and a same-binding override reads as the same", async ({
  page,
}) => {
  await signIn(page, users.owner);
  await restore(page);
  await page.goto("/settings/models");
  const effect = page.locator('[data-field="role-effect"]');
  await expect(effect).toContainText(
    "Only the executor's binding dispatches in this release. Other roles that differ from it don't take effect.",
  );
  await expect(effect).toContainText(
    "A summarizer that differs pauses the run with route_not_bound",
  );
  await expect(effect.locator('[data-role-effect="same"]')).toBeVisible();

  // A role that differs needs a saved choice this screen can't make now: saved-choice.spec.ts.
  await select(page, "coder").selectOption(TERRA);
  await page.getByRole("button", { name: "Save policy" }).click();
  await expect(page.locator("[data-policy-message]")).toContainText("Saved.");
  await expect(effect.locator('[data-role-effect="same"]')).toBeVisible();
  const stored = await storedPolicy(page);
  expect(stored.default_profile).toBe(TERRA);
  expect(stored.role_overrides).toEqual({ coder: TERRA });
  await restore(page);
});

test("a stale save is refused with a reload message, and the stored policy is unchanged", async ({
  page,
  signedInPage,
}) => {
  await signIn(page, users.owner);
  await restore(page);
  await page.goto("/settings/models");
  await expect(page.getByLabel("Workspace default")).toHaveValue(TERRA);

  // Someone else saves after this screen loaded.
  const other = await signedInPage(users.owner);
  await other.goto("/settings/models");
  await select(other, "coder").selectOption(TERRA);
  await other.getByRole("button", { name: "Save policy" }).click();
  await expect(other.locator("[data-policy-message]")).toContainText("Saved.");
  const stored = await storedPolicy(page);
  expect(stored.role_overrides).toEqual({ coder: TERRA });

  await select(page, "planner").selectOption(TERRA);
  await page.getByRole("button", { name: "Save policy" }).click();
  await expect(page.locator("[data-policy-message]")).toContainText(
    "Reload the page",
  );
  expect(await storedPolicy(page)).toEqual(stored);
  await restore(page);
});
