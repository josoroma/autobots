import { parseExecutionView, parseWorkflowList } from "@autobots/api-client";

import { expectNoA11yViolations } from "./support/a11y.ts";
import { getJson } from "./support/api.ts";
import { signIn, users } from "./support/auth.ts";
import { link, node } from "./support/builders.ts";
import { expect, test } from "./support/fixtures.ts";

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
  await signIn(page, users.owner);
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
  await page.getByRole("button", { name: "Publish", exact: true }).click();
  await expect(page.locator('[data-message="editor"]')).toContainText(
    "foreach_bound_required",
  );
  await expect(
    page.getByRole("heading", { name: "Run a version" }).locator(".."),
  ).toContainText("Publish a version first");

  await page.getByLabel("Graph").fill(JSON.stringify(LOOP));
  await page.getByRole("button", { name: "Validate" }).click();
  await expect(page.locator('[data-validation="valid"]')).toBeVisible();
  await expectNoA11yViolations(page);
  await page.getByRole("button", { name: "Publish", exact: true }).click();
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
  const execution = () =>
    getJson(page, {
      path: `/api/v1/workflow-executions/${id}`,
      parse: parseExecutionView,
    });
  const before = await execution();
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
  // A reply that isn't what was asked for doesn't stop polling or read as live. R-27: it says the
  // page and the service disagree, beside the last known state.
  await page.route("**/api/v1/workflow-executions/**", (route) =>
    route.fulfill({ status: 200, body: "<html>not it</html>" }),
  );
  await expect(page.locator("[data-connection]")).toHaveAttribute(
    "data-connection",
    "reconnecting",
    { timeout: 10_000 },
  );
  await expect(page.locator('[data-reason="out_of_date"]')).toHaveText(
    "This page and the local service disagree. Reload after updating.",
  );
  await expect(page.locator("[data-binding]")).toContainText("Version 1");
  await page.unroute("**/api/v1/workflow-executions/**");
  await expect(page.locator("[data-connection]")).toHaveAttribute(
    "data-connection",
    "live",
    { timeout: 10_000 },
  );
  await expect(page.locator("[data-reason]")).toHaveCount(0);
  await page.reload();
  await expect(page.locator('[data-emission="up#0.value.0"]')).toContainText(
    "A",
  );
  const after = await execution();
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
  await expectNoA11yViolations(page);
});

test("a failed branch is shown as failed, with what it blocked", async ({
  page,
}) => {
  test.setTimeout(60_000);
  await signIn(page, users.owner);
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
  await page.getByRole("button", { name: "Publish", exact: true }).click();
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
  asOwner: owner,
  asOwnerB: other,
}) => {
  const flows = await getJson(owner, {
    path: "/api/v1/workflows",
    parse: parseWorkflowList,
  });
  const flow = flows.workflows[0];
  if (flow === undefined) throw new Error("Workspace A has no workflow.");
  await other.goto(`/workflows/${flow.id}`);
  await expect(other.locator('[data-state="unavailable"]')).toBeVisible();
  await other.goto("/workflow-executions/00000000-0000-4000-8000-000000000000");
  const state = other.locator('[data-state="unavailable"]');
  await expect(state).toBeVisible();
  // R-27: a missing execution and a refusal say which, and reading again can't change either.
  await expect(state).toHaveAttribute("data-reason", "not_found");
  await expect(state).toHaveText("That execution is not available.");
  await other.route("**/api/v1/workflow-executions/**", (route) =>
    route.fulfill({
      status: 403,
      json: { code: "not_a_member", message: "Members only, arranged." },
    }),
  );
  await other.reload();
  await expect(state).toHaveAttribute("data-reason", "denied");
  await expect(state).toHaveText("Members only, arranged.");
  await expect(state.getByRole("button", { name: "Retry" })).toHaveCount(0);
});
