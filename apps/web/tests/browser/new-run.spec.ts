import type { Page } from "@playwright/test";

import { expectNoA11yViolations, WCAG_22_AA } from "./support/a11y.ts";
import { signIn, users } from "./support/auth.ts";
import { expect, test } from "./support/fixtures.ts";

// US-15.23, PRD-Studio SH-02 and Decision 0022 D3 and D16.
const MODIFIER = process.platform === "darwin" ? "Meta" : "Control";

function watchPosts(page: Page): string[] {
  const posts: string[] = [];
  page.on("request", (request) => {
    if (request.method() !== "GET")
      posts.push(`${request.method()} ${request.url()}`);
  });
  return posts;
}

const goal = (page: Page) =>
  page.getByRole("textbox", { name: "Goal", exact: true });

test("New run follows the skip link with its ⇧⌘O hint, and opens Home's composer with focus in the goal", async ({
  page,
}) => {
  await signIn(page, users.ops);
  await page.goto("/runs");
  const posts = watchPosts(page);
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to content" }),
  ).toBeFocused();
  await page.keyboard.press("Tab");
  const button = page.getByRole("button", { name: "New run" });
  await expect(button).toBeFocused();
  await expect(button).toContainText("⇧⌘O");
  await expect(button).toHaveAttribute(
    "aria-keyshortcuts",
    "Shift+Meta+O Shift+Control+O",
  );
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/$/);
  await expect(goal(page)).toBeFocused();
  // On Home itself, the button moves focus to the goal.
  await button.click();
  await expect(goal(page)).toBeFocused();
  expect(posts).toEqual([]);
  await expectNoA11yViolations(page, { extraTags: WCAG_22_AA });
});

test("⇧⌘O opens Home's composer from another screen", async ({ page }) => {
  await signIn(page, users.ops);
  await page.goto("/workflows");
  const posts = watchPosts(page);
  await page.locator("body").click({ position: { x: 5, y: 5 } });
  await page.keyboard.press(`Shift+${MODIFIER}+KeyO`);
  await expect(page).toHaveURL(/\/$/);
  await expect(goal(page)).toBeFocused();
  await expect(page.getByRole("button", { name: "New run" })).toContainText(
    "⇧⌘O",
  );
  expect(posts).toEqual([]);
});

test("⇧⌘O in a text field does nothing, and the field keeps its content and focus", async ({
  page,
}) => {
  await signIn(page, users.ops);
  await page.goto("/runs");
  const filter = page.getByRole("searchbox", {
    name: "Filter by goal or Expert",
  });
  await filter.fill("kept text");
  await filter.focus();
  await page.keyboard.press(`Shift+${MODIFIER}+KeyO`);
  await page.waitForTimeout(400);
  await expect(page).toHaveURL(/\/runs$/);
  await expect(filter).toBeFocused();
  await expect(filter).toHaveValue("kept text");
});
