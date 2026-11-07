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

test("Tools sits directly before Settings and lists tools by group", async ({
  page,
}) => {
  await signedIn(page, "/");
  const labels = await page
    .getByRole("navigation")
    .getByRole("link")
    .allTextContents();
  const trimmed = labels.map((label) => label.trim());
  expect(trimmed.indexOf("Tools")).toBe(trimmed.indexOf("Settings") - 1);
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
  const github = page.locator('[data-tool="create_github_issue"]');
  await expect(github).toContainText("Unavailable: key not set");
  await expect(github.locator('[data-field="repair"]')).toHaveText(
    "Set GITHUB_REPOSITORY and GITHUB_TOKEN in the worker's environment, then restart the worker and the API.",
  );
  const browse = page.locator('[data-tool="browse_goal"]');
  await expect(browse).toContainText("Unavailable: disabled by policy");
  await expect(browse.locator('[data-field="repair"]')).toHaveText(
    "Disabled until the isolated browser executor is qualified and turned on. See the operations runbook.",
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
    "GITHUB_REPOSITORY, GITHUB_TOKEN, from the worker's environment",
  );
  await expect(page.getByText("Unavailable: key not set")).toBeVisible();
});
