import AxeBuilder from "@axe-core/playwright";
import {
  expect,
  test,
  type Browser,
  type BrowserContext,
  type Page,
} from "@playwright/test";
import { execFileSync } from "node:child_process";

// US-15.21, PRD-Studio SE-02 and SE-05 to SE-07.
const EMAIL_A = process.env.AUTOBOTS_TEST_OWNER_EMAIL ?? "";
const PASSWORD_A = process.env.AUTOBOTS_TEST_OWNER_PASSWORD ?? "";
const EMAIL_C = process.env.AUTOBOTS_TEST_MEMBER_EMAIL ?? "";
const PASSWORD_C = process.env.AUTOBOTS_TEST_MEMBER_PASSWORD ?? "";
// A member of workspace A only, as a member of two would first have to choose one.
const EMAIL_F = process.env.AUTOBOTS_TEST_READER_EMAIL ?? "";
const PASSWORD_F = process.env.AUTOBOTS_TEST_READER_PASSWORD ?? "";
const OPS_EMAIL = process.env.AUTOBOTS_TEST_OPS_EMAIL ?? "";
const OPS_PASSWORD = process.env.AUTOBOTS_TEST_OPS_PASSWORD ?? "";
const OPS_WORKSPACE = process.env.AUTOBOTS_TEST_OPS_WORKSPACE ?? "";
const WEB = process.env.AUTOBOTS_WEB_URL ?? "";

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

async function axe(page: Page): Promise<void> {
  const scan = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(scan.violations).toEqual([]);
}

test("Settings lists its sections and links to Models and Operations", async ({
  page,
}) => {
  await signIn(page, EMAIL_C, PASSWORD_C);
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
    "Operations",
  ]);
  for (const [name, path] of [
    ["Notifications", "/settings/notifications"],
    ["Account", "/settings/account"],
    ["Data on this Mac", "/settings/data"],
    ["Keyboard", "/settings/keyboard"],
    ["Models", "/settings/models"],
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
  await signIn(page, EMAIL_C, PASSWORD_C);
  await page.goto("/settings/keyboard");
  const rows = page.locator("[data-shortcut]");
  await expect(rows).toHaveCount(7);
  const listed = await rows.evaluateAll((items) =>
    items.map((item) => ({
      keys: [...item.querySelectorAll("kbd")].map((key) => key.textContent),
      action: item.querySelector("dd")?.textContent ?? "",
    })),
  );
  expect(listed.map((item) => item.keys.join(" "))).toEqual([
    "⌘ K",
    "J",
    "K",
    "↓ ↑",
    "⌘ ↵",
    "⌘ ⌫",
    "Tab",
  ]);
  for (const item of listed) expect(item.action.length).toBeGreaterThan(10);
  expect(listed[0]?.action).toContain("Search");
  expect(listed[4]?.action).toContain("Approve");
  expect(listed[5]?.action).toContain("Reject");
  await axe(page);
});

test("Data on this Mac is read-only for a member and the owner, and only the owner is offered Operations", async ({
  browser,
}) => {
  const texts: string[] = [];
  for (const [email, password, owner] of [
    [EMAIL_F, PASSWORD_F, false],
    [EMAIL_A, PASSWORD_A, true],
  ] as const) {
    const context = await browser.newContext();
    const page = await context.newPage();
    await signIn(page, email, password);
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
    await context.close();
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

function arrangeWaiting(label: string): Record<string, string> {
  const printed = execFileSync(
    process.env.AUTOBOTS_TEST_PYTHON ?? "",
    [
      (process.env.AUTOBOTS_TEST_OPS_HELPER ?? "").replace(
        "operations_live.py",
        "notify_live.py",
      ),
      OPS_WORKSPACE,
      label,
    ],
    {
      env: {
        ...process.env,
        AUTOBOTS_DATABASE_URL: process.env.AUTOBOTS_TEST_RUNTIME_URL ?? "",
        PYTHONPATH: process.env.AUTOBOTS_TEST_PYTHONPATH ?? "",
      },
      encoding: "utf8",
    },
  );
  return JSON.parse(printed.trim().split("\n").at(-1) ?? "{}");
}

async function watching(
  browser: Browser,
  granted: boolean,
  settingOn: boolean,
): Promise<{ context: BrowserContext; page: Page; requests: string[] }> {
  const context = await browser.newContext();
  await context.addInitScript(SPY, granted ? "granted" : "denied");
  const page = await context.newPage();
  const requests: string[] = [];
  page.on("request", (request) => requests.push(request.url()));
  await signIn(page, OPS_EMAIL, OPS_PASSWORD);
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
  return { context, page, requests };
}

test("with the setting on and permission granted, each run that starts waiting raises one notification, and nothing leaves the Mac", async ({
  browser,
}) => {
  expect(OPS_WORKSPACE, "the ops-n workspace is arranged").not.toBe("");
  const { context, page, requests } = await watching(browser, true, true);
  const made = arrangeWaiting("granted");
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
  const origin = new URL(WEB).origin;
  expect(requests.filter((url) => !url.startsWith(origin))).toEqual([]);
  await context.close();
});

for (const [label, granted, settingOn] of [
  ["permission not granted", false, true],
  ["setting off", true, false],
] as const) {
  test(`with the ${label}, no notification is shown`, async ({ browser }) => {
    const { context, page } = await watching(browser, granted, settingOn);
    arrangeWaiting(label.replaceAll(" ", "-"));
    await page.waitForTimeout(10_000);
    expect(
      await page.evaluate(
        () => (window as unknown as { __notes: unknown[] }).__notes.length,
      ),
    ).toBe(0);
    await context.close();
  });
}
