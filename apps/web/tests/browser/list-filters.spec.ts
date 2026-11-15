import type { Page } from "@playwright/test";

import { signIn, users } from "./support/auth.ts";
import { expect, test } from "./support/fixtures.ts";

// R-67, XWEB-13: every list keeps its filters and selection in the URL, so a reload, Back and a shared
// link keep them, and following the list's own link in the sidebar starts it afresh, search box
// included (WTAP-15). Read-only, against the users scripts/qualify_identity.py arranges: Runs-r's
// 101 runs, 24 of which need the person, and the Experts user's four Experts.

/** A section's link in the sidebar. Approvals' name ends with its "N waiting" badge (US-15.5). */
function sidebarLink(page: Page, name: string) {
  return page
    .getByRole("navigation", { name: "Main" })
    .getByRole("link", { name: new RegExp(`^${name}(\\s|$)`) });
}

test("Runs keeps its status and search in the URL, and its sidebar link starts it afresh", async ({
  page,
}) => {
  await signIn(page, users.runs);
  await page.goto("/runs");
  const tab = (id: string) => page.locator(`[data-group="${id}"]`);
  const rows = page.locator("[data-run]");
  const search = page.getByPlaceholder("Filter by goal or Expert");
  await tab("needs_you").click();
  await expect(page).toHaveURL(/[?&]group=needs_you/);
  await expect(rows).toHaveCount(24);
  await page.reload();
  await expect(tab("needs_you")).toHaveAttribute("aria-pressed", "true");
  await expect(rows).toHaveCount(24);

  await tab("all").click();
  await expect(page).not.toHaveURL(/group=/);
  await search.fill("fully reported");
  await expect(page).toHaveURL(/[?&]q=fully\+reported/);
  await expect(rows).toHaveCount(1);
  await page.reload();
  await expect(search).toHaveValue("fully reported");
  await expect(rows).toHaveCount(1);

  await sidebarLink(page, "Runs").click();
  await expect(page).toHaveURL(/\/runs$/);
  await expect(search).toHaveValue("");
  await expect(tab("all")).toHaveAttribute("aria-pressed", "true");
  await expect(rows).toHaveCount(100);
});

test("Experts keeps its filter and search in the URL, and Back returns to them", async ({
  page,
}) => {
  await signIn(page, users.experts);
  await page.goto("/experts");
  const filter = (id: string) => page.locator(`[data-filter="${id}"]`);
  const expert = (name: string) =>
    page.getByRole("main").getByRole("link", { name, exact: true });
  const search = page.getByPlaceholder("Search Experts");
  await filter("outside").click();
  await expect(page).toHaveURL(/[?&]tab=outside/);
  await page.reload();
  await expect(filter("outside")).toHaveAttribute("aria-pressed", "true");
  await expect(expert("Issue triager")).toBeVisible();
  await expect(expert("Brief writer")).toHaveCount(0);

  await filter("all").click();
  await search.fill("brief");
  await expect(page).toHaveURL(/[?&]q=brief/);
  await expect(page).not.toHaveURL(/tab=/);
  await page.reload();
  await expect(search).toHaveValue("brief");
  await expect(expert("Brief writer")).toBeVisible();
  await expect(expert("Issue triager")).toHaveCount(0);

  await expert("Brief writer").click();
  await expect(page).toHaveURL(/\/experts\/[0-9a-f-]{36}/);
  await page.goBack();
  await expect(search).toHaveValue("brief");
  await expect(expert("Issue triager")).toHaveCount(0);
  await sidebarLink(page, "Experts").click();
  await expect(search).toHaveValue("");
  await expect(expert("Issue triager")).toBeVisible();
});

test("Approvals keeps its tab in the URL", async ({ page }) => {
  await signIn(page, users.owner);
  await page.goto("/approvals");
  await page.locator('[data-tab="decided"]').click();
  await expect(page).toHaveURL(/[?&]tab=decided/);
  await page.reload();
  await expect(page.locator('[data-tab="decided"]')).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await sidebarLink(page, "Approvals").click();
  await expect(page.locator('[data-tab="waiting"]')).toHaveAttribute(
    "aria-pressed",
    "true",
  );
});

test("the Tools link clears the catalog's search box with its filter", async ({
  page,
}) => {
  await signIn(page, users.owner);
  await page.goto("/tools");
  const search = page.getByRole("searchbox", { name: "Search" });
  const tools = page.locator("[data-tool]");
  await search.fill("calculate");
  await expect(page).toHaveURL(/[?&]q=calculate/);
  await expect(tools).toHaveCount(1);
  await sidebarLink(page, "Tools").click();
  await expect(page).toHaveURL(/\/tools$/);
  await expect(search).toHaveValue("");
  await expect.poll(() => tools.count()).toBeGreaterThan(1);
});
