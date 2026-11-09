import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// US-14.2 against the real API app with an arranged membership, run by scripts/qualify_web.py.
// That API's environment has no GitHub variables, so create_github_issue reads key_missing.

const ORIGIN = process.env.AUTOBOTS_WEB_URL ?? "";
const SESSION_A = process.env.AUTOBOTS_TEST_SESSION_A ?? "";

async function signedIn(page: Page, path: string): Promise<void> {
  await page
    .context()
    .addCookies([{ name: "autobots.session", value: SESSION_A, url: ORIGIN }]);
  await page.goto(path);
}

async function noViolations(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(
    results.violations.map((item) => `${item.id}: ${item.nodes.length}`),
  ).toEqual([]);
}

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
  await noViolations(page);
});

test("filters live in the URL, so a view can be linked", async ({ page }) => {
  await signedIn(page, "/tools");
  await page.getByLabel("Group").selectOption("files");
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
  await noViolations(page);

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
  const version = await (
    await page.request.get("/api/v1/tools/calculate/versions/1")
  ).json();
  expect(JSON.parse(copied)).toEqual(version.input_schema);
  expect(version.guide.what).toBe(
    "Computes the sum, mean, minimum or maximum of a list of numbers.",
  );
  await noViolations(page);

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
    await noViolations(page);
  }
});
