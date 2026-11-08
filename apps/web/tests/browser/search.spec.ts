import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// US-15.22, PRD-Studio SR-01 and Decision 0022 D3. scripts/qualify_identity.py names a run's goal, an
// Expert and a workflow with "read" in the ops-n workspace, and a run and an Expert in another workspace.
const OPS_EMAIL = process.env.AUTOBOTS_TEST_OPS_EMAIL ?? "";
const OPS_PASSWORD = process.env.AUTOBOTS_TEST_OPS_PASSWORD ?? "";
const IDS = JSON.parse(process.env.AUTOBOTS_TEST_SEARCH_IDS ?? "{}") as Record<
  string,
  string
>;
const MODIFIER = process.platform === "darwin" ? "Meta" : "Control";

async function signIn(page: Page): Promise<void> {
  await page.goto("/sign-in");
  await page.getByLabel("Email").fill(OPS_EMAIL);
  await page.getByLabel("Password").fill(OPS_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText(/Signed in, with access to/)).toBeVisible();
}

test("one endpoint returns typed results of each kind from this workspace only", async ({
  page,
}) => {
  expect(IDS.run, "the search records are arranged").toBeTruthy();
  await signIn(page);
  const reply = await page.request.get("/api/v1/search?q=read");
  expect(reply.status()).toBe(200);
  const body = await reply.json();
  const results = body.results as {
    kind: string;
    id: string;
    title: string;
    href: string;
  }[];
  const of = (kind: string) => results.filter((item) => item.kind === kind);
  expect(of("run").map((item) => item.id)).toContain(IDS.run);
  expect(of("expert").map((item) => item.id)).toEqual([IDS.expert]);
  expect(of("workflow").map((item) => item.id)).toEqual([IDS.workflow]);
  expect(of("tool").length).toBeGreaterThan(0);
  for (const tool of of("tool"))
    expect(`${tool.title} ${tool.id}`.toLowerCase()).toContain("read");
  expect(of("run").find((item) => item.id === IDS.run)?.href).toBe(
    `/runs/${IDS.run}`,
  );
  const text = JSON.stringify(body);
  for (const elsewhere of [
    IDS.other_run,
    IDS.other_expert,
    "Read another workspace plan",
    "Reader elsewhere",
  ])
    expect(text).not.toContain(elsewhere);
});

test("⌘K and the Search button after the skip link open the palette, and ⌘K in a text field does nothing", async ({
  page,
}) => {
  await signIn(page);
  await page.goto("/");
  const dialog = page.getByRole("dialog", { name: "Search" });
  await page.locator("body").click({ position: { x: 5, y: 5 } });
  await page.keyboard.press(`${MODIFIER}+k`);
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("listbox", { name: "Results" })).toBeAttached();
  await expect(
    dialog.getByRole("combobox", { name: "Search this workspace" }),
  ).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();

  // The skip link is the first stop, then New run, then Search with its key hint.
  await page.goto("/runs");
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to content" }),
  ).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "New run" })).toBeFocused();
  await page.keyboard.press("Tab");
  const button = page.getByRole("button", { name: "Search" });
  await expect(button).toBeFocused();
  await expect(button).toContainText("⌘K");
  await expect(button).toHaveAttribute("aria-keyshortcuts", "Meta+K Control+K");
  await page.keyboard.press("Enter");
  await expect(dialog).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(button).toBeFocused();

  // With focus in a text field, ⌘K does nothing. The list settles first, so its arrival can't take the
  // focus back from the field before the key is pressed.
  await page.waitForLoadState("networkidle");
  const filter = page.getByRole("searchbox", {
    name: "Filter by goal or Expert",
  });
  await filter.focus();
  await expect(filter).toBeFocused();
  await page.keyboard.press(`${MODIFIER}+k`);
  await page.waitForTimeout(300);
  await expect(dialog).toBeHidden();
});

test("arrows move the announced option, Enter opens it, and Escape returns focus", async ({
  page,
}) => {
  await signIn(page);
  await page.goto("/runs");
  await page.keyboard.press(`${MODIFIER}+k`);
  const dialog = page.getByRole("dialog", { name: "Search" });
  const box = dialog.getByRole("combobox");
  await box.fill("read");
  await expect(dialog.locator('[data-field="search-status"]')).toHaveText(
    /^\d+ results?\.$/,
  );
  const options = dialog.getByRole("option");
  expect(await options.count()).toBeGreaterThan(2);
  await expect(options.nth(0)).toHaveAttribute("aria-selected", "true");
  await expect(box).toHaveAttribute(
    "aria-activedescendant",
    (await options.nth(0).getAttribute("id")) ?? "",
  );
  await page.keyboard.press("ArrowDown");
  await expect(options.nth(1)).toHaveAttribute("aria-selected", "true");
  await expect(options.nth(0)).toHaveAttribute("aria-selected", "false");
  await expect(box).toHaveAttribute(
    "aria-activedescendant",
    (await options.nth(1).getAttribute("id")) ?? "",
  );
  await page.keyboard.press("ArrowUp");
  await expect(options.nth(0)).toHaveAttribute("aria-selected", "true");
  // The workflow's option, by moving to it with the arrows.
  const kinds = await options.evaluateAll((items) =>
    items.map((item) => item.getAttribute("data-kind")),
  );
  const target = kinds.indexOf("workflow");
  for (let step = 0; step < target; step += 1)
    await page.keyboard.press("ArrowDown");
  await expect(options.nth(target)).toHaveAttribute("aria-selected", "true");
  const scan = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(scan.violations).toEqual([]);
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(new RegExp(`/workflows/${IDS.workflow}$`));
  await expect(dialog).toBeHidden();

  // Reopened from a focused link, Escape gives focus back to that link.
  await page.goto("/runs");
  const runs = page
    .getByRole("navigation", { name: "Main" })
    .getByRole("link", { name: "Runs" });
  await runs.focus();
  await page.keyboard.press(`${MODIFIER}+k`);
  await expect(dialog).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(runs).toBeFocused();
});
