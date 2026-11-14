import type { BrowserContext, Page } from "@playwright/test";

import { expectNoA11yViolations, WCAG_22_AA } from "./support/a11y.ts";
import { signIn, users, type Credentials } from "./support/auth.ts";
import { need, webOrigin } from "./support/env.ts";
import { objectOf, runDbHelper } from "./support/db-helpers.ts";
import { expect, test } from "./support/fixtures.ts";

// US-15.21, PRD-Studio SE-02 and SE-05 to SE-07.

async function axe(page: Page): Promise<void> {
  await expectNoA11yViolations(page, { extraTags: WCAG_22_AA });
}

test("Settings lists its sections and links to Models, Keys & vars and Operations", async ({
  page,
}) => {
  await signIn(page, users.member);
  await page.goto("/settings");
  const nav = page.getByRole("navigation", { name: "Settings sections" });
  await expect(nav.locator('[data-field="settings-sections"] a')).toHaveText([
    "Appearance",
    "Notifications",
    "Account",
    "Data on this Mac",
    "Keyboard",
  ]);
  await expect(nav.getByRole("link", { name: "Appearance" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  await expect(nav.locator('[data-field="settings-elsewhere"] a')).toHaveText([
    "Models",
    "Keys & vars",
    "Operations",
  ]);
  for (const [name, path] of [
    ["Notifications", "/settings/notifications"],
    ["Account", "/settings/account"],
    ["Data on this Mac", "/settings/data"],
    ["Keyboard", "/settings/keyboard"],
    ["Models", "/settings/models"],
    ["Keys & vars", "/settings/keys-and-vars"],
    ["Operations", "/operations"],
  ] as const)
    await expect(nav.getByRole("link", { name, exact: true })).toHaveAttribute(
      "href",
      path,
    );
  await nav.getByRole("link", { name: "Keyboard" }).click();
  await expect(page).toHaveURL(/\/settings\/keyboard$/);
  await expect(nav.getByRole("link", { name: "Keyboard" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  await axe(page);
});

test("Keyboard lists each shortcut with its keys and what it does", async ({
  page,
}) => {
  await signIn(page, users.member);
  await page.goto("/settings/keyboard");
  const rows = page.locator("[data-shortcut]");
  await expect(rows).toHaveCount(8);
  const listed = await rows.evaluateAll((items) =>
    items.map((item) => ({
      keys: [...item.querySelectorAll("kbd")].map((key) => key.textContent),
      action: item.querySelector("dd")?.textContent ?? "",
    })),
  );
  expect(listed.map((item) => item.keys.join(" "))).toEqual([
    "⇧ ⌘ O",
    "⌘ K",
    "J",
    "K",
    "↓ ↑",
    "⌘ ↵",
    "⌘ ⌫",
    "Tab",
  ]);
  for (const item of listed) expect(item.action.length).toBeGreaterThan(10);
  expect(listed[0]?.action).toContain("composer");
  expect(listed[1]?.action).toContain("Search");
  expect(listed[5]?.action).toContain("Approve");
  expect(listed[6]?.action).toContain("Reject");
  await axe(page);
});

test("Data on this Mac is read-only for a member and the owner, and only the owner is offered Operations", async ({
  signedInPage,
}) => {
  // A member of workspace A only, as a member of two would first have to choose one.
  const texts: string[] = [];
  for (const [user, owner] of [
    [users.reader, false],
    [users.owner, true],
  ] as const) {
    const page = await signedInPage(user);
    await page.goto("/settings/data");
    const summary = page.locator('[data-field="retention-summary"]');
    await expect(summary.locator('[data-field="run-retention"]')).toBeVisible();
    texts.push(
      `${await summary.locator('[data-field="run-retention"]').innerText()} ${await summary.locator('[data-field="receipt-retention"]').innerText()}`,
    );
    await expect(
      summary.locator("input, select, textarea, button"),
    ).toHaveCount(0);
    await expect(summary.locator('[data-field="operations-link"]')).toHaveCount(
      owner ? 1 : 0,
    );
    if (owner)
      await expect(
        summary.getByRole("link", { name: "Change retention on Operations" }),
      ).toHaveAttribute("href", "/operations");
    else
      await expect(summary.locator('[data-field="owner-only"]')).toHaveText(
        "Only the workspace owner can change retention.",
      );
    // The summary can't be written through its own route.
    const put = await page.request.put("/api/v1/retention", {
      data: { run_days: 1 },
    });
    expect(put.status()).toBeGreaterThanOrEqual(400);
    await axe(page);
  }
  expect(texts[0]).toBe(texts[1]);
});

// Headless Chromium reports notification permission as denied whatever is granted, so the browser's
// permission is arranged here: the stub answers with the state each test sets, and records each
// notification instead of showing it.
const SPY = (permission: string) => {
  const notes: { title: string; tag: string | undefined }[] = [];
  (window as unknown as { __notes: typeof notes }).__notes = notes;
  class Spy {
    constructor(title: string, options?: { tag?: string }) {
      notes.push({ title, tag: options?.tag });
    }
    static get permission(): string {
      return permission;
    }
    static requestPermission(): Promise<string> {
      return Promise.resolve(permission);
    }
  }
  Object.defineProperty(window, "Notification", {
    value: Spy,
    configurable: true,
  });
};

/** tests/db/notify_live.py makes two of the ops-n workspace's runs start waiting, and names them. */
function arrangeWaiting(
  label: string,
): Promise<{ waiting_approval: string; waiting_input: string }> {
  return runDbHelper(
    "notify_live.py",
    [need("AUTOBOTS_TEST_OPS_WORKSPACE"), label],
    objectOf({ waiting_approval: "string", waiting_input: "string" }),
  );
}

/** A signed-in page whose notifications the spy records, on Home after its first poll. */
async function watching(
  context: BrowserContext,
  user: Credentials,
  { granted, settingOn }: { granted: boolean; settingOn: boolean },
): Promise<{ page: Page; requests: string[] }> {
  await context.addInitScript(SPY, granted ? "granted" : "denied");
  const page = await context.newPage();
  const requests: string[] = [];
  page.on("request", (request) => requests.push(request.url()));
  await signIn(page, user);
  if (settingOn) {
    await page.goto("/settings/notifications");
    await page
      .getByRole("checkbox", { name: "Tell me when a run waits for me" })
      .check();
    await expect(page.locator('[data-field="notify-permission"]')).toHaveText(
      granted ? "This browser allows the app's notifications." : /blocks|asks/,
    );
  }
  await page.goto("/");
  // One poll notes what already waits, so only what newly waits is told.
  await page.waitForTimeout(5_000);
  return { page, requests };
}

test("with the setting on and permission granted, each run that starts waiting raises one notification, and nothing leaves the Mac", async ({
  openContext,
}) => {
  const { page, requests } = await watching(await openContext(), users.ops, {
    granted: true,
    settingOn: true,
  });
  const made = await arrangeWaiting("granted");
  await expect
    .poll(
      async () =>
        page.evaluate(
          () =>
            (window as unknown as { __notes: { title: string }[] }).__notes
              .length,
        ),
      { timeout: 15_000 },
    )
    .toBe(2);
  const notes = await page.evaluate(
    () =>
      (window as unknown as { __notes: { title: string; tag: string }[] })
        .__notes,
  );
  expect(notes.map((note) => note.title).sort()).toEqual([
    "A run waits for your approval",
    "A run waits for your input",
  ]);
  expect(notes.map((note) => note.tag).sort()).toEqual(
    [
      `${made.waiting_approval}:waiting_approval`,
      `${made.waiting_input}:waiting_input`,
    ].sort(),
  );
  // Polling again tells nothing twice.
  await page.waitForTimeout(5_000);
  expect(
    await page.evaluate(
      () => (window as unknown as { __notes: unknown[] }).__notes.length,
    ),
  ).toBe(2);
  const origin = webOrigin();
  expect(requests.filter((url) => !url.startsWith(origin))).toEqual([]);
});

for (const [label, granted, settingOn] of [
  ["permission not granted", false, true],
  ["setting off", true, false],
] as const) {
  test(`with the ${label}, no notification is shown`, async ({
    openContext,
  }) => {
    const { page } = await watching(await openContext(), users.ops, {
      granted,
      settingOn,
    });
    await arrangeWaiting(label.replaceAll(" ", "-"));
    await page.waitForTimeout(10_000);
    expect(
      await page.evaluate(
        () => (window as unknown as { __notes: unknown[] }).__notes.length,
      ),
    ).toBe(0);
  });
}
