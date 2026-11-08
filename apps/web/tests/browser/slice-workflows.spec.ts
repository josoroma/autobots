import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const EMAIL_A = process.env.AUTOBOTS_TEST_OWNER_EMAIL ?? "";
const PASSWORD_A = process.env.AUTOBOTS_TEST_OWNER_PASSWORD ?? "";
const EMAIL_B = process.env.AUTOBOTS_TEST_OWNER_B_EMAIL ?? "";
const PASSWORD_B = process.env.AUTOBOTS_TEST_OWNER_B_PASSWORD ?? "";

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

const node = (id: string, block: string, config: object = {}) => ({
  id,
  block,
  version: 1,
  config,
});
const link = (
  source: string,
  sourcePort: string,
  target: string,
  targetPort: string,
) => ({
  source,
  source_port: sourcePort,
  target,
  target_port: targetPort,
});

const LOOP = {
  nodes: [
    node("in", "input", { type: "list" }),
    node("each", "foreach", { max_items: 5 }),
    node("up", "transform", { operation: "upper" }),
    node("all", "join"),
    node("ok", "approval"),
    node("out", "output"),
  ],
  links: [
    link("in", "value", "each", "items"),
    link("each", "item", "up", "value"),
    link("up", "value", "all", "value"),
    link("all", "items", "ok", "value"),
    link("ok", "value", "out", "value"),
  ],
};

test("a graph is validated, published, run and monitored, and the monitor only reads", async ({
  page,
}) => {
  test.setTimeout(90_000);
  await signIn(page, EMAIL_A, PASSWORD_A);
  await page.goto("/workflows");
  await page.getByLabel("Name").fill("Monitored flow");
  await page.getByRole("button", { name: "Create" }).click();
  await expect(page).toHaveURL(/\/workflows\/[0-9a-f-]{36}/);
  await expect(page.locator('[data-block="foreach"]')).toContainText(
    "foreach v1",
  );

  // Typed errors are visible before anything can publish.
  const broken = {
    ...LOOP,
    nodes: LOOP.nodes.map((item) =>
      item.id === "each" ? node("each", "foreach") : item,
    ),
  };
  await page.getByLabel("Graph").fill(JSON.stringify(broken));
  await page.getByRole("button", { name: "Validate" }).click();
  await expect(
    page.locator('[data-error="foreach_bound_required"]'),
  ).toContainText("at each");
  await page.getByRole("button", { name: "Publish" }).click();
  await expect(page.locator('[data-message="editor"]')).toContainText(
    "foreach_bound_required",
  );
  await expect(
    page.getByRole("heading", { name: "Run a version" }).locator(".."),
  ).toContainText("Publish a version first");

  await page.getByLabel("Graph").fill(JSON.stringify(LOOP));
  await page.getByRole("button", { name: "Validate" }).click();
  await expect(page.locator('[data-validation="valid"]')).toBeVisible();
  const axe = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(axe.violations.map((violation) => violation.id)).toEqual([]);
  await page.getByRole("button", { name: "Publish" }).click();
  await expect(page.locator('[data-message="editor"]')).toContainText(
    "Published as version 1",
  );

  await page.getByLabel("Inputs").fill(JSON.stringify({ in: ["a", "b"] }));
  await page.getByRole("button", { name: "Run this version" }).click();
  await expect(page).toHaveURL(/\/workflow-executions\//);
  await expect(page.locator("[data-binding]")).toContainText("Version 1");

  // The fixture worker runs it up to the approval step.
  await expect(page.locator('[data-instance="up#1"]')).toHaveAttribute(
    "data-status",
    "succeeded",
    { timeout: 30_000 },
  );
  await expect(page.locator('[data-emission="up#0.value.0"]')).toContainText(
    "A",
  );
  await expect(page.locator('[data-emission="up#1.value.0"]')).toContainText(
    "B",
  );
  await expect(page.locator('[data-emission="all.items.0"]')).toContainText(
    '["A", "B"]',
  );
  await expect(page.locator("[data-run-status]")).toHaveAttribute(
    "data-run-status",
    "waiting_approval",
    { timeout: 15_000 },
  );
  await expect(page.locator('[data-instance="out"]')).toHaveAttribute(
    "data-status",
    "waiting",
  );

  // A dropped connection and a reconnect read saved state, and start nothing.
  const url = page.url();
  const id = url.split("/").at(-1) ?? "";
  const before = await (
    await page.request.get(`/api/v1/workflow-executions/${id}`)
  ).json();
  await page.route("**/api/v1/workflow-executions/**", (route) =>
    route.abort(),
  );
  await expect(page.locator("[data-connection]")).toHaveAttribute(
    "data-connection",
    "reconnecting",
    { timeout: 10_000 },
  );
  await page.unroute("**/api/v1/workflow-executions/**");
  await expect(page.locator("[data-connection]")).toHaveAttribute(
    "data-connection",
    "live",
    { timeout: 10_000 },
  );
  // A reply that isn't what was asked for doesn't stop polling or read as live.
  await page.route("**/api/v1/workflow-executions/**", (route) =>
    route.fulfill({ status: 200, body: "<html>not it</html>" }),
  );
  await expect(page.locator("[data-connection]")).toHaveAttribute(
    "data-connection",
    "reconnecting",
    { timeout: 10_000 },
  );
  await page.unroute("**/api/v1/workflow-executions/**");
  await expect(page.locator("[data-connection]")).toHaveAttribute(
    "data-connection",
    "live",
    { timeout: 10_000 },
  );
  await page.reload();
  await expect(page.locator('[data-emission="up#0.value.0"]')).toContainText(
    "A",
  );
  const after = await (
    await page.request.get(`/api/v1/workflow-executions/${id}`)
  ).json();
  expect(after.emissions).toEqual(before.emissions);
  expect(after.instances).toEqual(before.instances);

  // Approving continues it through the inbox.
  await page.goto("/approvals");
  await page
    .locator("[data-approval-item]")
    .filter({ hasText: "workflow_approval" })
    .first()
    .click();
  await page
    .locator("[data-approval]")
    .getByRole("button", { name: "Approve" })
    .click();
  await expect(page.locator('[data-message="decision"]')).toContainText(
    "Only this exact request",
  );
  await page.goto(url);
  await expect(page.locator("[data-run-status]")).toHaveAttribute(
    "data-run-status",
    "succeeded",
    { timeout: 30_000 },
  );
  await expect(page.locator('[data-emission="out.value.0"]')).toContainText(
    '["A", "B"]',
  );
  const axeMonitor = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(axeMonitor.violations.map((violation) => violation.id)).toEqual([]);
});

test("a failed branch is shown as failed, with what it blocked", async ({
  page,
}) => {
  test.setTimeout(60_000);
  await signIn(page, EMAIL_A, PASSWORD_A);
  await page.goto("/workflows");
  await page.getByLabel("Name").fill("Failing flow");
  await page.getByRole("button", { name: "Create" }).click();
  await expect(page).toHaveURL(/\/workflows\/[0-9a-f-]{36}/);
  const graph = {
    nodes: [
      node("in", "input", { type: "json" }),
      node("up", "transform", { operation: "upper" }),
      node("out", "output"),
    ],
    links: [
      link("in", "value", "up", "value"),
      link("up", "value", "out", "value"),
    ],
  };
  await page.getByLabel("Graph").fill(JSON.stringify(graph));
  await page.getByRole("button", { name: "Publish" }).click();
  await expect(page.locator('[data-message="editor"]')).toContainText(
    "Published",
  );
  await page.getByLabel("Inputs").fill(JSON.stringify({ in: 5 }));
  await page.getByRole("button", { name: "Run this version" }).click();
  await expect(page.locator('[data-instance="up"]')).toHaveAttribute(
    "data-status",
    "failed",
    { timeout: 30_000 },
  );
  await expect(page.locator('[data-instance="up"]')).toContainText(
    "transform input invalid",
  );
  await expect(page.locator('[data-instance="out"]')).toHaveAttribute(
    "data-status",
    "blocked",
  );
  await expect(page.locator("[data-run-status]")).toHaveAttribute(
    "data-run-status",
    "failed",
  );
});

test("another workspace can't see a workflow or an execution", async ({
  browser,
}) => {
  const owner = await (await browser.newContext()).newPage();
  await signIn(owner, EMAIL_A, PASSWORD_A);
  const flows = await (await owner.request.get("/api/v1/workflows")).json();
  const flow = flows.workflows[0];
  const other = await (await browser.newContext()).newPage();
  await signIn(other, EMAIL_B, PASSWORD_B);
  await other.goto(`/workflows/${flow.id}`);
  await expect(other.locator('[data-state="unavailable"]')).toBeVisible();
  await other.goto("/workflow-executions/00000000-0000-4000-8000-000000000000");
  await expect(other.locator('[data-state="unavailable"]')).toBeVisible();
});
