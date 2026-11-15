/**
 * Workspace A's states that more than one suite reads: its OpenRouter key, retention windows and model
 * policy. A suite that needs one checks it through the API in beforeAll, so a broken chain fails at its
 * source, and a suite that changes one restores it in afterAll, which runs whatever the tests' outcome
 * (TWEB-01). A restore reads the state first and writes only when it differs, so a run whose tests all
 * pass writes nothing more than they do. Hooks get worker fixtures only, so each signs in on a context
 * of its own and closes it.
 */
import {
  parseLocalStatus,
  parseModelPolicyState,
  parseProviderStatus,
  type ProviderStatus,
} from "@autobots/api-client";
import { expect, type Browser, type Page } from "@playwright/test";

import { getJson, send } from "./api.ts";
import { signIn, users, type Credentials } from "./auth.ts";
import { test } from "./fixtures.ts";
import { disconnectProviderKey } from "./keys.ts";

const POLICY = "/api/settings/model-policy";
/** The scripted worker's route, which the slice suites start from. */
const ORIGINAL_PROFILE = "openrouter_terra";

/** Signs in as `user` on a context of its own, runs `act`, then closes the context. */
export async function signedInFor<T>(
  browser: Browser,
  user: Credentials,
  act: (page: Page) => Promise<T>,
): Promise<T> {
  const context = await browser.newContext();
  try {
    const page = await context.newPage();
    await signIn(page, user);
    return await act(page);
  } finally {
    await context.close();
  }
}

/** The workspace's OpenRouter key, as Settings → Models reads it. */
export function providerStatus(page: Page): Promise<ProviderStatus> {
  return getJson(page, {
    path: "/api/settings/model-providers",
    parse: parseProviderStatus,
  });
}

/**
 * Declares that the enclosing describe's tests start with no saved key in workspace A: a beforeAll
 * checks it through the API, and fails with `why`, which names what should have removed it.
 */
export function startsWithoutProviderKey(why: string): void {
  test.beforeAll(async ({ browser }) => {
    const status = await signedInFor(browser, users.owner, providerStatus);
    expect(status.source, why).toBe("none");
  });
}

/** Fails unless workspace A has a saved key that authenticated, as settings.spec.ts leaves it. */
export async function expectAuthenticatedProviderKey(
  browser: Browser,
): Promise<void> {
  const status = await signedInFor(browser, users.owner, providerStatus);
  expect(
    [status.source, status.auth_status],
    "settings.spec.ts leaves workspace A a saved key that authenticated",
  ).toEqual(["app", "configured"]);
}

/** Disconnects workspace A's saved key, if one is left. */
export async function removeProviderKeyIfAny(browser: Browser): Promise<void> {
  await signedInFor(browser, users.owner, async (page) => {
    if ((await providerStatus(page)).source === "app") {
      await disconnectProviderKey(page);
    }
  });
}

/** Saves "keep everything" in Operations, if workspace A has a retention window saved. */
export async function restoreRetentionIfSaved(browser: Browser): Promise<void> {
  await signedInFor(browser, users.owner, async (page) => {
    const { retention } = await getJson(page, {
      path: "/api/v1/operations/local-status",
      parse: parseLocalStatus,
    });
    if (
      (retention?.run_days ?? null) === null &&
      (retention?.receipt_days ?? null) === null
    ) {
      return;
    }
    await page.goto("/operations");
    await page.getByLabel(/Run content/).fill("");
    await page.getByLabel(/Retry keys/).fill("");
    await page.getByRole("button", { name: "Save retention" }).click();
    await expect(page.getByText(/Saved\. Nothing is removed/)).toBeVisible();
  });
}

/** Saves the original model policy, Terra with no role overrides, whatever is stored. */
export async function restoreModelPolicy(page: Page): Promise<void> {
  const current = await getJson(page, {
    path: POLICY,
    parse: parseModelPolicyState,
  });
  await send(page, {
    method: "PUT",
    path: POLICY,
    key: null,
    data: {
      expected_version: current.version,
      default_profile: ORIGINAL_PROFILE,
      role_overrides: {},
    },
    status: 200,
    parse: parseModelPolicyState,
  });
}

/** Saves the original model policy, if workspace A's differs from it. */
export async function restoreModelPolicyIfChanged(
  browser: Browser,
): Promise<void> {
  await signedInFor(browser, users.owner, async (page) => {
    const current = await getJson(page, {
      path: POLICY,
      parse: parseModelPolicyState,
    });
    if (
      current.default_profile === ORIGINAL_PROFILE &&
      Object.keys(current.role_overrides).length === 0
    ) {
      return;
    }
    await restoreModelPolicy(page);
  });
}
