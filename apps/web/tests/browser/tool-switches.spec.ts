import { parseToolCatalog, type ToolCatalog } from "@autobots/api-client";
import type { Page } from "@playwright/test";

import { expectNoA11yViolations } from "./support/a11y.ts";
import { csrfHeaders, expectRefusal } from "./support/api.ts";
import { signIn, users } from "./support/auth.ts";
import { expect, test } from "./support/fixtures.ts";
import { signedInFor } from "./support/state.ts";

// US-14.24, Decision 0033 W1 to W5, against the disposable identity stack run by
// scripts/qualify_identity.py. That stack has no SerpApi key, so the Google tools that need one
// read key_missing while on, and google_extract, which needs none, reads available. Every switch
// this suite turns off is turned back on, so the suites after it start with everything on.

const CATALOG = "/api/v1/tools";
const GOOGLE = [
  "google_search",
  "google_map",
  "google_extract",
  "google_crawl",
] as const;

async function catalog(page: Page): Promise<ToolCatalog> {
  const reply = await page.request.get(CATALOG);
  expect(reply.status()).toBe(200);
  return parseToolCatalog(await reply.json());
}

async function putGroup(page: Page, enabled: boolean, version: number) {
  return page.request.put(`${CATALOG}/groups/google/switch`, {
    headers: await csrfHeaders(page),
    data: { enabled, expected_version: version },
  });
}

function row(page: Page, toolId: string) {
  return page.locator(`[data-tool="${toolId}"]`);
}

function groupSection(page: Page) {
  return page.locator('[data-group="google"]');
}

// Whatever a test that failed part way left off is turned back on (TWEB-01).
test.afterAll(async ({ browser }) => {
  await signedInFor(browser, users.owner, async (page) => {
    const found = await catalog(page);
    const group = found.groups.find((item) => item.group === "google");
    if (group?.switch && !group.switch.enabled) {
      expect((await putGroup(page, true, group.switch.version)).status()).toBe(
        200,
      );
    }
    for (const tool of found.tools) {
      if (tool.switch && !tool.switch.enabled) {
        const reply = await page.request.put(
          `${CATALOG}/${tool.tool_id}/switch`,
          {
            headers: await csrfHeaders(page),
            data: { enabled: true, expected_version: tool.switch.version },
          },
        );
        expect(reply.status(), tool.tool_id).toBe(200);
      }
    }
  });
});

test("the owner turns the Google group off and on with the keyboard, in both themes", async ({
  page,
}) => {
  await signIn(page, users.owner);
  const before = await catalog(page);
  expect(before.viewer_can_switch).toBe(true);
  for (const toolId of GOOGLE) {
    const tool = before.tools.find((item) => item.tool_id === toolId);
    expect(tool?.switch, toolId).toEqual({
      enabled: true,
      version: 0,
      by: null,
    });
  }
  for (const toolId of ["propose_plan", "complete_task"]) {
    expect(
      before.tools.find((item) => item.tool_id === toolId)?.switch ?? null,
    ).toBeNull();
  }

  for (const theme of ["light", "dark"] as const) {
    await page.addInitScript(
      (stored) => window.localStorage.setItem("autobots.theme", stored),
      theme,
    );
    await page.goto("/tools");
    await expect(page.locator("html")).toHaveClass(new RegExp(theme));
    const groupSwitch = groupSection(page).getByRole("switch", {
      name: "Google group for this workspace",
    });
    await expect(groupSwitch).toHaveAttribute("aria-checked", "true");
    await expect(groupSwitch).toHaveText("On");

    // Off, by keyboard: every Google tool reads off with its group, in words.
    await groupSwitch.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("status")).toContainText("Saved");
    await expect(groupSwitch).toHaveAttribute("aria-checked", "false");
    await expect(groupSwitch).toHaveText("Off");
    for (const toolId of GOOGLE) {
      await expect(
        row(page, toolId).locator('[data-field="switch-state"]'),
      ).toHaveText("Off with its group");
      await expect(row(page, toolId)).toContainText(
        "Unavailable: disabled by policy",
      );
      await expect(
        row(page, toolId).locator('[data-field="repair"]'),
      ).toContainText("Its group is turned off for this workspace");
    }
    await expectNoA11yViolations(page);

    // Back on, by keyboard: google_extract, which needs no key, is available again.
    await groupSwitch.focus();
    await page.keyboard.press("Space");
    await expect(groupSwitch).toHaveAttribute("aria-checked", "true");
    await expect(row(page, "google_extract")).toContainText("Available");
    await expect(
      row(page, "google_extract").getByRole("switch", {
        name: "Google Extract for this workspace",
      }),
    ).toHaveText("On");
    await expectNoA11yViolations(page);
  }
});

test("a member sees each switch's state but can't change it, and a stale change is refused", async ({
  page,
  browser,
}) => {
  // The owner turns google_crawl off, so the member has a state to read.
  let version = 0;
  await signedInFor(browser, users.owner, async (owner) => {
    const crawl = (await catalog(owner)).tools.find(
      (item) => item.tool_id === "google_crawl",
    );
    const reply = await owner.request.put(`${CATALOG}/google_crawl/switch`, {
      headers: await csrfHeaders(owner),
      data: { enabled: false, expected_version: crawl?.switch?.version ?? 0 },
    });
    expect(reply.status()).toBe(200);
    version = (await reply.json()).version;
    // The version it last read is stale now.
    await expectRefusal(
      await owner.request.put(`${CATALOG}/google_crawl/switch`, {
        headers: await csrfHeaders(owner),
        data: { enabled: true, expected_version: version - 1 },
      }),
      { status: 409, code: "stale_version" },
    );
  });

  // A member of workspace A only, as a member of two would first have to choose one.
  await signIn(page, users.reader);
  const seen = await catalog(page);
  expect(seen.viewer_can_switch).toBe(false);
  await page.goto("/tools");
  await expect(page.getByRole("switch")).toHaveCount(0);
  await expect(
    row(page, "google_crawl").locator('[data-field="switch-state"]'),
  ).toHaveText("Off for this workspace");
  await expect(
    row(page, "google_search").locator('[data-field="switch-state"]'),
  ).toHaveText("On for this workspace");
  await expect(
    groupSection(page).locator('[data-field="group-switch-state"]'),
  ).toHaveText("Group on for this workspace");
  await expectRefusal(
    await page.request.put(`${CATALOG}/google_crawl/switch`, {
      headers: await csrfHeaders(page),
      data: { enabled: true, expected_version: version },
    }),
    { status: 403, code: "owner_required" },
  );
  await expectNoA11yViolations(page);

  // The owner turns it back on at the current version.
  await signedInFor(browser, users.owner, async (owner) => {
    const reply = await owner.request.put(`${CATALOG}/google_crawl/switch`, {
      headers: await csrfHeaders(owner),
      data: { enabled: true, expected_version: version },
    });
    expect(reply.status()).toBe(200);
    expect(await reply.json()).toEqual({
      enabled: true,
      version: version + 1,
      by: null,
    });
  });
});
