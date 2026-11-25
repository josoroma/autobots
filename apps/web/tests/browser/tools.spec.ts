import { parseToolDescriptor } from "@autobots/api-client";
import type { Page, Route } from "@playwright/test";

import { expectNoA11yViolations } from "./support/a11y.ts";
import { getJson } from "./support/api.ts";
import { addSessionCookie } from "./support/auth.ts";
import { need } from "./support/env.ts";
import { expect, test } from "./support/fixtures.ts";

// US-14.2 against the real API app with an arranged membership, run by scripts/qualify_web.py.
// That API's environment has no GitHub variables, so create_github_issue reads key_missing.

async function signedIn(page: Page, path: string): Promise<void> {
  await addSessionCookie(page, need("AUTOBOTS_TEST_SESSION_A"));
  await page.goto(path);
}

const OUT_OF_DATE =
  "This page and the local service disagree. Reload after updating.";
const DOWN = {
  status: 503,
  json: {
    code: "service_unavailable",
    message: "The local API is unavailable.",
  },
};

test("Tools sits under Build after Workflows and lists tools by group", async ({
  page,
}) => {
  await signedIn(page, "/");
  const navigation = page.getByRole("navigation");
  const labels = await navigation.getByRole("link").allTextContents();
  // A pending-approvals badge reads "N waiting" after its link name (US-15.5).
  const trimmed = labels.map((label) =>
    label.replace(/\s*\d+ waiting$/, "").trim(),
  );
  // US-15.1: three groups, in order, with Tools directly after Workflows.
  expect(trimmed).toEqual([
    "Home",
    "Runs",
    "Approvals",
    "Experts",
    "Workflows",
    "Tools",
    "Operations",
    "Models",
    "Settings",
  ]);
  for (const [group, links] of [
    ["Work", ["Home", "Runs", "Approvals"]],
    ["Build", ["Experts", "Workflows", "Tools"]],
    ["System", ["Operations", "Models", "Settings"]],
  ] as const) {
    const list = navigation.getByRole("list", { name: group });
    await expect(list).toBeVisible();
    expect(
      (await list.getByRole("link").allTextContents()).map((l) =>
        l.replace(/\s*\d+ waiting$/, "").trim(),
      ),
    ).toEqual([...links]);
  }
  await expect(
    navigation.getByRole("link", { name: "Home", exact: true }),
  ).toHaveAttribute("aria-current", "page");
  // The skip link stays first, and activating it moves focus into the main content.
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to content" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await page.keyboard.press("Tab");
  expect(
    await page.evaluate(() => document.activeElement?.closest("main") !== null),
  ).toBe(true);
  await page.getByRole("link", { name: "Tools", exact: true }).click();
  await expect(page).toHaveURL(/\/tools$/);
  await expect(
    page.getByRole("heading", { name: "Tools", level: 1 }),
  ).toBeVisible();
  for (const group of ["Planning", "General", "Files", "Connectors"]) {
    await expect(
      page.getByRole("heading", { name: group, level: 2 }),
    ).toBeVisible();
  }
  const calculate = page.locator('[data-tool="calculate"]');
  await expect(calculate).toContainText("calculate v1");
  await expect(calculate).toContainText("Available");
  await expect(calculate).toContainText("Pure");
  await expectNoA11yViolations(page);
});

test("filters live in the URL, so a view can be linked", async ({ page }) => {
  await signedIn(page, "/tools");
  // By role, since each group's switch is labelled "... group for this workspace" (US-14.24), and the
  // label around this select holds its options too.
  await page
    .getByRole("combobox", { name: "Group", exact: true })
    .selectOption("files");
  await expect(page).toHaveURL(/group=files/);
  await expect(page.locator("[data-group]")).toHaveCount(1);
  await expect(page.locator('[data-tool="read_run_file"]')).toBeVisible();
  await page.goto("/tools?availability=disabled_by_policy");
  await expect(page.getByLabel("Availability")).toHaveValue(
    "disabled_by_policy",
  );
  await expect(page.locator("[data-tool]")).toHaveCount(1);
  await expect(page.locator('[data-tool="browse_goal"]')).toBeVisible();
});

// PRD-Tool-Catalog TG-02 and WTAP-13: a deep link to a tool the filters hide still opens it, and on
// closing, focus falls back to the first tool the list shows, since the tool's own link isn't there.
test("closing a deep-linked tool the filters hide puts focus on the list's first tool", async ({
  page,
}) => {
  await signedIn(page, "/tools?group=files&tool=calculate");
  await expect(page.locator('[data-tool="calculate"]')).toHaveCount(0);
  const dialog = page.getByRole("dialog", { name: "Calculate" });
  await expect(dialog).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(page).not.toHaveURL(/[?&]tool=/);
  await expect(page).toHaveURL(/group=files/);
  await expect(
    page.locator("[data-tool]").first().getByRole("link"),
  ).toBeFocused();
});

test("unavailable tools say so in words, with their repair", async ({
  page,
}) => {
  await signedIn(page, "/tools");
  // PRD-Studio GH-07: every GitHub tool, with both variables, the token's permissions and a restart.
  for (const id of [
    "create_github_issue",
    "github_list_pull_requests",
    "github_list_workflow_runs",
    "github_search_issues",
    "github_read_file",
  ]) {
    const github = page.locator(`[data-tool="${id}"]`);
    await expect(github).toContainText("Unavailable: key not set");
    await expect(github.locator('[data-field="repair"]')).toHaveText(
      "Save them in Settings → Keys & vars, or set GITHUB_REPOSITORY and GITHUB_TOKEN in .env. The token needs these permissions on that repository only: Issues: read and write, Pull requests: read and write, Contents: read and write, Actions: read, Metadata: read. After a change to .env, restart the worker and the API.",
    );
  }
  const browse = page.locator('[data-tool="browse_goal"]');
  await expect(browse).toContainText("Unavailable: disabled by policy");
  await expect(browse.locator('[data-field="repair"]')).toHaveText(
    "Disabled until the isolated browser executor is qualified and browsing is turned on in Settings → Keys & vars or .env. See the operations runbook.",
  );
});

test("a tool's detail lists its versions and every field", async ({ page }) => {
  await signedIn(page, "/tools/calculate");
  await expect(page.getByRole("heading", { name: "Calculate" })).toBeVisible();
  await expect(page.getByLabel("Version")).toHaveValue("1");
  const inputs = page.locator('[data-fields="input"]');
  const operation = inputs.locator('[data-field-path="operation"]');
  await expect(operation).toContainText("Required");
  await expect(operation).toContainText('enum ["sum","mean","min","max"]');
  await expect(operation).toContainText("Shown");
  const values = inputs.locator('[data-field-path="values"]');
  await expect(values).toContainText("number[]");
  await expect(values).toContainText("Not shown");
  await expect(values).toContainText("minItems 1");
  await expect(
    page.locator('[data-fields="output"] [data-field-path="result"]'),
  ).toContainText("Required");
  await page.getByText("JSON Schema").click();
  await expect(page.locator("pre")).toContainText('"CalculateInput"');
  await expectNoA11yViolations(page);

  await signedIn(page, "/tools/create_github_issue");
  await expect(page.locator('[data-field="key"]')).toHaveText(
    "GITHUB_REPOSITORY, GITHUB_TOKEN, not set",
  );
  await expect(page.getByText("Unavailable: key not set")).toBeVisible();
});

// US-15.7 and US-14.20: group counts, a text filter in the URL, the tool's modal and Copy schema.
test("group counts, text filter, the tool modal and Copy schema", async ({
  page,
  context,
}) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await signedIn(page, "/tools");
  for (const section of await page.locator("[data-group]").all()) {
    const rows = await section.locator("[data-tool]").count();
    await expect(section.locator('[data-field="count"]')).toHaveText(
      `${rows} ${rows === 1 ? "tool" : "tools"}`,
    );
  }
  await page.getByRole("searchbox", { name: "Search" }).fill("calculate");
  await expect(page).toHaveURL(/[?&]q=calculate/);
  await expect(page.locator("[data-tool]")).toHaveCount(1);
  await expect(page.locator('[data-tool="calculate"]')).toBeVisible();

  const link = page
    .locator('[data-tool="calculate"]')
    .getByRole("link", { name: "Calculate" });
  await link.click();
  await expect(page).toHaveURL(/[?&]tool=calculate/);
  await expect(page).toHaveURL(/[?&]q=calculate/);
  const dialog = page.getByRole("dialog", { name: "Calculate" });
  await expect(dialog).toBeVisible();
  expect(
    await dialog.evaluate((element) => element.tagName.toLowerCase()),
  ).toBe("dialog");
  await expect(
    page.getByRole("complementary", { name: "Tool detail" }),
  ).toHaveCount(0);
  // Decision 0026 G1: what, when and why, then the inputs and outputs.
  await expect(dialog.locator('[data-guide="what"]')).toHaveText(
    "Computes the sum, mean, minimum or maximum of a list of numbers.",
  );
  await expect(dialog.locator('[data-guide="when"]')).not.toBeEmpty();
  await expect(dialog.locator('[data-guide="why"]')).not.toBeEmpty();
  const inputs = dialog.locator('[data-fields="input"]');
  await expect(inputs.locator('[data-field-path="operation"]')).toContainText(
    "Required",
  );
  await expect(inputs.locator('[data-field-path="operation"]')).toContainText(
    "Shown",
  );
  await expect(
    dialog.locator('[data-fields="output"] [data-field-path="result"]'),
  ).toContainText("Required");
  await expect(
    dialog.getByRole("link", { name: "Open as a page" }),
  ).toHaveAttribute("href", "/tools/calculate");

  await dialog.getByRole("button", { name: "Copy schema" }).click();
  await expect(dialog.locator('[data-message="copied"]')).toHaveText(
    "Copied the input schema of version 1.",
  );
  const copied = await page.evaluate(() => navigator.clipboard.readText());
  const version = await getJson(page, {
    path: "/api/v1/tools/calculate/versions/1",
    parse: parseToolDescriptor,
  });
  expect(JSON.parse(copied)).toEqual(version.input_schema);
  expect(version.guide.what).toBe(
    "Computes the sum, mean, minimum or maximum of a list of numbers.",
  );
  await expectNoA11yViolations(page);

  // Escape, Close and a click on the backdrop each close it, and focus returns to the link.
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(page).not.toHaveURL(/[?&]tool=/);
  await expect(link).toBeFocused();
  await link.click();
  await page
    .getByRole("dialog", { name: "Calculate" })
    .getByRole("button", { name: "Close" })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(link).toBeFocused();
  await link.click();
  await expect(page.getByRole("dialog", { name: "Calculate" })).toBeVisible();
  await page.mouse.click(4, 4);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(link).toBeFocused();

  await page.goto("/tools/calculate");
  await expect(page.getByRole("heading", { name: "Calculate" })).toBeVisible();
  await expect(page.locator('[data-guide="what"]')).toBeVisible();
});

test("a tool's modal opens from its URL and passes axe in both themes", async ({
  page,
}) => {
  for (const theme of ["light", "dark"] as const) {
    await page.addInitScript(
      (stored) => window.localStorage.setItem("autobots.theme", stored),
      theme,
    );
    await signedIn(page, "/tools?tool=create_github_issue");
    const dialog = page.getByRole("dialog", { name: "Create GitHub issue" });
    await expect(dialog).toBeVisible();
    await expect(dialog.locator('[data-field="repair"]')).toContainText(
      "Settings → Keys & vars",
    );
    await expect(dialog.locator('[data-guide="when"]')).not.toBeEmpty();
    await expect(page.locator("html")).toHaveClass(new RegExp(theme));
    await expectNoA11yViolations(page);
  }
});

// R-27: each way the catalog can fail reads differently, and only an outage offers Retry. The
// replies are arranged with page.route on the catalog's own read.
test("the catalog says why it can't be read, and Retry reads it again", async ({
  page,
}) => {
  let arranged: Parameters<Route["fulfill"]>[0] | null = null;
  await page.route("**/api/v1/tools", (route) =>
    arranged === null ? route.continue() : route.fulfill(arranged),
  );
  const logged: unknown[] = [];
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    if (!message.text().startsWith("This page and the local service")) return;
    void message
      .args()[1]
      ?.jsonValue()
      .then((value: unknown) => logged.push(value));
  });
  const state = page.locator('[data-state="unavailable"]');
  for (const [reply, reason, words] of [
    [
      {
        status: 401,
        json: { code: "not_signed_in", message: "Sign in first." },
      },
      "signed_out",
      "You're signed out. Sign in to see the tool catalog.",
    ],
    [
      {
        status: 403,
        json: { code: "not_a_member", message: "Members only, arranged." },
      },
      "denied",
      "Members only, arranged.",
    ],
    [
      {
        status: 200,
        json: { schema_version: 1, catalog_digest: "arranged-value" },
      },
      "out_of_date",
      OUT_OF_DATE,
    ],
  ] as const) {
    arranged = reply;
    await signedIn(page, "/tools");
    await expect(state).toHaveAttribute("data-reason", reason);
    await expect(state.getByRole("alert")).toHaveText(words);
    await expect(state.getByRole("button", { name: "Retry" })).toHaveCount(0);
    await expect(state.getByRole("link", { name: "Sign in" })).toHaveCount(
      reason === "signed_out" ? 1 : 0,
    );
  }
  // The console names the schema and the field, never a value from the reply.
  await expect.poll(() => logged.length).toBeGreaterThan(0);
  expect(logged[0]).toMatchObject({
    event: "web.contract_mismatch",
    schema: "ToolCatalog",
  });
  expect(JSON.stringify(logged)).not.toContain("arranged-value");

  arranged = DOWN;
  await signedIn(page, "/tools");
  await expect(state).toHaveAttribute("data-reason", "unavailable");
  await expect(state.getByRole("alert")).toHaveText(
    "The tool catalog can't be read right now. Check that the local services are running, then try again.",
  );
  arranged = null;
  await state.getByRole("button", { name: "Retry" }).click();
  await expect(page.locator('[data-tool="calculate"]')).toBeVisible();
  await expect(state).toHaveCount(0);
});
