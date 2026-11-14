import type { Page, Route } from "@playwright/test";

import { expectNoA11yViolations } from "./support/a11y.ts";
import { signIn, users } from "./support/auth.ts";
import { needList } from "./support/env.ts";
import { expect, test } from "./support/fixtures.ts";

// US-15.10, PRD-Studio HM-01 and HM-04 and Decision 0022 D9 and D14, against an owner arranged by
// scripts/qualify_identity.py: an America/Costa_Rica workspace (UTC-6, no daylight saving), the
// display name Ada and seven runs a minute apart, newest first:
// waiting_input, paused, waiting_approval (two pending approvals), running with a plan,
// succeeded with US$0.07 charged, succeeded, failed.
const homeRuns = () => needList("AUTOBOTS_TEST_HOME_RUNS");
const homeApprovals = () => needList("AUTOBOTS_TEST_HOME_APPROVALS");

// A local Costa Rica time on 2026-11-09, as the instant the browser's clock is fixed to.
function costaRica(hour: number, minute: number): Date {
  return new Date(Date.UTC(2026, 10, 9, hour + 6, minute));
}

async function greetingAt(page: Page, at: Date): Promise<string> {
  await page.clock.setFixedTime(at);
  await page.goto("/");
  const greeting = page.locator('[data-field="greeting"]');
  await expect(greeting).toContainText("Ada");
  return (await greeting.textContent()) ?? "";
}

test.describe.configure({ mode: "serial" });

test("the greeting follows the workspace's timezone, then the heading", async ({
  page,
}) => {
  await signIn(page, users.home);
  for (const [hour, expected] of [
    [9, "Good morning, Ada"],
    [14, "Good afternoon, Ada"],
    [20, "Good evening, Ada"],
  ] as const) {
    expect(await greetingAt(page, costaRica(hour, 0))).toBe(expected);
    const heading = page.getByRole("heading", { level: 1 });
    await expect(heading).toHaveText("What should we work on?");
    // The greeting comes first, and then the heading.
    const order = await page.evaluate(() => {
      const greeting = document.querySelector('[data-field="greeting"]');
      const title = document.querySelector("h1");
      return greeting !== null && title !== null
        ? greeting.compareDocumentPosition(title) &
            Node.DOCUMENT_POSITION_FOLLOWING
        : 0;
    });
    expect(order).toBeGreaterThan(0);
  }
  await expectNoA11yViolations(page);
});

test("the greeting's boundaries", async ({ page }) => {
  await signIn(page, users.home);
  for (const [hour, minute, expected] of [
    [4, 59, "Good evening"],
    [5, 0, "Good morning"],
    [11, 59, "Good morning"],
    [12, 0, "Good afternoon"],
    [17, 59, "Good afternoon"],
    [18, 0, "Good evening"],
  ] as const) {
    expect(await greetingAt(page, costaRica(hour, minute))).toBe(
      `${expected}, Ada`,
    );
  }
});

test("Needs you lists pending approvals and a run waiting for input, not a paused run", async ({
  page,
}) => {
  await signIn(page, users.home);
  const runs = homeRuns();
  const pending = homeApprovals();
  await page.goto("/");
  const needs = page.locator('[data-field="needs-you"]');
  await expect(needs.locator("[data-needs-approval]")).toHaveCount(2);
  await expect(needs.locator("[data-needs-reply]")).toHaveCount(1);
  const reply = needs.locator(`[data-needs-reply="${runs[0]}"]`);
  await expect(reply).toContainText("Answer the rate question");
  await expect(
    reply.getByRole("link", { name: "Reply on the run" }),
  ).toHaveAttribute("href", `/runs/${runs[0]}`);
  // Paused counts as Active (D9), so it isn't here.
  await expect(needs).not.toContainText("Compare paused rates");
  await expect(needs.locator(`[data-needs-reply="${runs[1]}"]`)).toHaveCount(0);
  for (const approval of pending) {
    const item = needs.locator(`[data-needs-approval="${approval}"]`);
    await expect(item).toContainText("create_github_issue");
    await expect(item).toContainText("Send the brief");
    await expect(item.getByRole("link", { name: "Review" })).toHaveAttribute(
      "href",
      `/approvals?approval=${approval}`,
    );
  }
  await expectNoA11yViolations(page);

  // Review opens that request, including one that isn't first in the list.
  for (const approval of [...pending].reverse()) {
    await page.goto("/");
    await needs
      .locator(`[data-needs-approval="${approval}"]`)
      .getByRole("link", { name: "Review" })
      .click();
    await expect(page).toHaveURL(`/approvals?approval=${approval}`);
    await expect(page.locator(`[data-approval="${approval}"]`)).toBeVisible();
  }
});

test("Recent runs lists the five newest with state, progress or spend, and a relative time", async ({
  page,
}) => {
  await signIn(page, users.home);
  await page.goto("/");
  const recent = page.locator('[data-field="recent-runs"] [data-recent-run]');
  await expect(recent).toHaveCount(5);
  const shown = await recent.evaluateAll((items) =>
    items.map((item) => item.getAttribute("data-recent-run")),
  );
  expect(shown).toEqual(homeRuns().slice(0, 5));
  const row = (index: number) => recent.nth(index);
  const expected = [
    ["Answer the rate question", "Waiting for input", "US$0.00 spent"],
    ["Compare paused rates", "Paused", "US$0.00 spent"],
    ["Send the brief", "Waiting for approval", "US$0.00 spent"],
    ["Plan two tasks", "Running", "1 of 2 tasks"],
    ["Spent seven cents", "Succeeded", "US$0.07 spent"],
  ] as const;
  for (const [index, [goal, state, progress]] of expected.entries()) {
    await expect(row(index).getByRole("link")).toHaveText(goal);
    await expect(row(index).locator('[data-field="state"]')).toHaveText(state);
    await expect(row(index).locator('[data-field="progress"]')).toHaveText(
      progress,
    );
    await expect(row(index).locator('[data-field="when"]')).toHaveText(
      /^(just now|\d+ minutes? ago|\d+ hours? ago)$/,
    );
  }
  await expect(page.locator('[data-field="recent-runs"]')).not.toContainText(
    "Older sixth run",
  );
  await expect(page.locator('[data-field="recent-runs"]')).not.toContainText(
    "Oldest seventh run",
  );
  await expectNoA11yViolations(page);
});

// R-27: the three reads behind Needs you and Recent runs fail as one, say why, and Retry reads them
// again. The replies are arranged with page.route on the approvals read.
test("Needs you and Recent runs say why they can't be read, and Retry reads them again", async ({
  page,
}) => {
  await signIn(page, users.home);
  let arranged: Parameters<Route["fulfill"]>[0] | null = {
    status: 503,
    json: {
      code: "service_unavailable",
      message: "The local API is unavailable.",
    },
  };
  await page.route("**/api/v1/approvals", (route) =>
    arranged === null ? route.continue() : route.fulfill(arranged),
  );
  await page.goto("/");
  const state = page.locator('[data-state="unavailable"]');
  await expect(state).toHaveAttribute("data-reason", "unavailable");
  await expect(state.getByRole("alert")).toHaveText(
    "What needs you and recent runs can't be read right now. Check that the local services are running, then try again.",
  );
  await expect(page.locator('[data-field="needs-you"]')).toHaveCount(0);
  arranged = null;
  await state.getByRole("button", { name: "Retry" }).click();
  await expect(
    page.locator('[data-field="needs-you"] [data-needs-approval]'),
  ).toHaveCount(2);
  await expect(
    page.locator('[data-field="recent-runs"] [data-recent-run]'),
  ).toHaveCount(5);

  // A reply in another shape reads as out of date, not as an outage, and a 401 as signed out.
  arranged = { status: 200, json: { schema_version: 1, approvals: "x" } };
  await page.goto("/");
  await expect(state).toHaveAttribute("data-reason", "out_of_date");
  await expect(state.getByRole("alert")).toHaveText(
    "This page and the local service disagree. Reload after updating.",
  );
  await expect(state.getByRole("button", { name: "Retry" })).toHaveCount(0);
  arranged = {
    status: 401,
    json: { code: "not_signed_in", message: "Sign in first." },
  };
  await page.goto("/");
  await expect(state).toHaveAttribute("data-reason", "signed_out");
  await expect(state.getByRole("link", { name: "Sign in" })).toHaveAttribute(
    "href",
    "/sign-in",
  );
});
