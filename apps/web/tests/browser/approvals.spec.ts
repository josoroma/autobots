import {
  parseApprovalList,
  parseApprovalResult,
  parsePendingApprovals,
  type ApprovalList,
} from "@autobots/api-client";
import type { Page, Route } from "@playwright/test";

import { expectNoA11yViolations } from "./support/a11y.ts";
import { expectRefusal, getJson, send, writeHeaders } from "./support/api.ts";
import { signIn, users } from "./support/auth.ts";
import { arranged } from "./support/env.ts";
import { expect, test } from "./support/fixtures.ts";
import { readRun } from "./support/runs.ts";

// Arranged by tests/db/approval_check.py through scripts/qualify_identity.py.
const approval = arranged({
  approve: "AUTOBOTS_TEST_APPROVAL_APPROVE",
  reject: "AUTOBOTS_TEST_APPROVAL_REJECT",
  hash: "AUTOBOTS_TEST_APPROVAL_HASH",
  run: "AUTOBOTS_TEST_APPROVAL_RUN",
  legacy: "AUTOBOTS_TEST_APPROVAL_LEGACY",
  legacyHash: "AUTOBOTS_TEST_APPROVAL_LEGACY_HASH",
  legacyRun: "AUTOBOTS_TEST_APPROVAL_LEGACY_RUN",
  loud: "AUTOBOTS_TEST_APPROVAL_LOUD",
  markdown: "AUTOBOTS_TEST_APPROVAL_MARKDOWN",
  expert: "AUTOBOTS_TEST_APPROVAL_EXPERT",
});
const POLICY_REASON =
  "This tool changes something outside this Mac, so policy holds each call for a person.";

function approvals(page: Page, query = ""): Promise<ApprovalList> {
  return getJson(page, {
    path: `/api/v1/approvals${query}`,
    parse: parseApprovalList,
  });
}

async function listed(page: Page, id: string) {
  const found = (await approvals(page)).approvals.find(
    (item) => item.id === id,
  );
  if (found === undefined) throw new Error(`${id} isn't listed as waiting`);
  return found;
}

// US-15.5: the inbox lists requests beside the selected one's detail, so a test selects it first.
async function open(page: Page, id: string) {
  await page.locator(`[data-approval-item="${id}"]`).click();
  const card = page.locator(`[data-approval="${id}"]`);
  await expect(card).toBeVisible();
  return card;
}

test("another workspace and a member can't decide", async ({
  asOwnerB: other,
  asMember: member,
}) => {
  const list = await approvals(other);
  expect(list.approvals.map((item) => item.id)).not.toContain(approval.approve);
  const decision = `/api/v1/approvals/${approval.approve}/decision`;
  const foreign = await other.request.post(decision, {
    headers: await writeHeaders(other, "foreign"),
    data: { decision: "approve", argument_hash: approval.hash },
  });
  expect(foreign.status()).toBe(404);
  const denied = await member.request.post(decision, {
    headers: await writeHeaders(member, "member"),
    data: { decision: "approve", argument_hash: approval.hash },
  });
  expect(denied.status()).toBe(403);
});

test("each request shows the policy's reason, its target, the exact action and its expiry", async ({
  page,
}) => {
  await signIn(page, users.owner);
  await page.goto("/approvals");
  const card = await open(page, approval.approve);
  await expect(card.locator("[data-approval-reason]")).toHaveText(
    `Why it's asking: ${POLICY_REASON}`,
  );
  await expect(card.locator("[data-approval-target]")).toHaveText(
    "Target: Mail to team@example.invalid",
  );
  await expect(card.locator("pre")).toContainText('"body": "hello"');
  await expect(card).toContainText(/Expires \d/);

  // What the model wrote stays in the request, and doesn't reach the reason.
  const loud = await open(page, approval.loud);
  await expect(loud.locator("pre")).toContainText("REASON FROM THE MODEL");
  await expect(loud.locator("[data-approval-reason]")).toHaveText(
    `Why it's asking: ${POLICY_REASON}`,
  );
});

test("each request shows who asked, its scope and its policy version, as stored with it", async ({
  page,
}) => {
  await signIn(page, users.owner);
  await page.goto("/approvals");
  const card = await open(page, approval.approve);
  await expect(card.locator("[data-approval-requester]")).toHaveText(
    'Requested by: you started this run, and Expert "Mail sender", version 2, proposed it.',
  );
  await expect(card.locator("[data-approval-scope]")).toContainText(
    "Scope when asked: tools mock_send version 1",
  );
  await expect(card.locator("[data-approval-policy]")).toHaveText(
    "Policy version: approval-policy/2, rule consequential external write.",
  );
  const shown = await listed(page, approval.approve);
  expect(shown.argument_hash).toBe(approval.hash);
  expect(shown.requester).toMatchObject({
    person_is_viewer: true,
    agent: "expert",
    expert_id: approval.expert,
    expert_version: 2,
  });
  expect(shown.scope_snapshot).toMatchObject({ tools: { mock_send: 1 } });
  // Another run in this workspace, with no Expert, names the coordinator.
  const other = await open(page, approval.reject);
  await expect(other.locator("[data-approval-requester]")).toContainText(
    "the coordinator proposed it",
  );
});

test("a request saved before these fields says so, and its decision stays bound to the hash shown", async ({
  page,
}) => {
  await signIn(page, users.owner);
  await page.goto("/approvals");
  const card = await open(page, approval.legacy);
  await expect(card.locator("[data-approval-reason]")).toContainText(
    "not recorded",
  );
  await expect(card.locator("[data-approval-target]")).toContainText(
    "not recorded",
  );
  for (const field of ["requester", "scope", "policy"]) {
    await expect(card.locator(`[data-approval-${field}]`)).toContainText(
      "not recorded",
    );
  }
  await expect(card.locator("pre")).toContainText("old@example.invalid");
  const tampered = await page.request.post(
    `/api/v1/approvals/${approval.legacy}/decision`,
    {
      headers: await writeHeaders(page, "legacy-tamper"),
      data: { decision: "approve", argument_hash: "0".repeat(64) },
    },
  );
  await expectRefusal(tampered, { status: 409, code: "approval_mismatch" });
  const shown = await listed(page, approval.legacy);
  expect(shown.argument_hash).toBe(approval.legacyHash);
  await card.getByRole("button", { name: "Reject" }).click();
  await expect(page.locator('[data-message="decision"]')).toContainText(
    "Rejected.",
  );
  const summary = await readRun(page, approval.legacyRun);
  expect(summary.status).not.toBe("waiting_approval");
});

test("the inbox shows the exact request, and a tampered decision releases nothing", async ({
  page,
}) => {
  await signIn(page, users.owner);
  await page.goto("/approvals");
  const card = await open(page, approval.approve);
  await expect(card).toContainText("mock_send, version 1");
  await expect(card).toContainText("team@example.invalid");
  await expect(card).toContainText("consequential external write");
  await expectNoA11yViolations(page);

  const tampered = await page.request.post(
    `/api/v1/approvals/${approval.approve}/decision`,
    {
      headers: await writeHeaders(page, "tamper"),
      data: { decision: "approve", argument_hash: "0".repeat(64) },
    },
  );
  await expectRefusal(tampered, { status: 409, code: "approval_mismatch" });
  const summary = await readRun(page, approval.run);
  expect(summary.status).toBe("waiting_approval");
});

// The decision in the first test is what the second, US-15.5's decided card, reads under Decided, so
// the second is skipped if the first fails (TWEB-07). The tests above read both requests still
// waiting, so they come first.
test.describe(() => {
  test.describe.configure({ mode: "serial" });

  test("an owner approves and rejects through the inbox, and a repeat changes nothing", async ({
    page,
  }) => {
    await signIn(page, users.owner);
    await page.goto("/approvals");
    await (
      await open(page, approval.approve)
    )
      .getByRole("button", { name: "Approve" })
      .click();
    await expect(page.locator('[data-message="decision"]')).toContainText(
      "Only this exact request",
    );
    await expect(
      page.locator(`[data-approval="${approval.approve}"]`),
    ).toHaveCount(0);
    await (
      await open(page, approval.reject)
    )
      .getByRole("button", { name: "Reject" })
      .click();
    await expect(page.locator('[data-message="decision"]')).toContainText(
      "won't run",
    );

    const summary = await readRun(page, approval.run);
    expect(summary.status).toBe("queued");
    const decision = `/api/v1/approvals/${approval.approve}/decision`;
    const again = await send(page, {
      path: decision,
      key: "again",
      data: { decision: "approve", argument_hash: approval.hash },
      status: 200,
      parse: parseApprovalResult,
    });
    expect(again.replayed).toBe(true);
    const opposite = await page.request.post(decision, {
      headers: await writeHeaders(page, "opposite"),
      data: { decision: "reject", argument_hash: approval.hash },
    });
    await expectRefusal(opposite, {
      status: 409,
      code: "approval_already_decided",
    });
    const history = await approvals(page, "?status=approved");
    expect(history.approvals.map((item) => item.id)).toContain(
      approval.approve,
    );
  });

  test("a decided request shows its run, task, expiry and who decided", async ({
    page,
  }) => {
    await signIn(page, users.owner);
    await page.goto("/approvals");
    const loaded = page.waitForResponse((reply) =>
      reply.url().includes("/api/v1/approvals?status=decided"),
    );
    await page.locator('[data-tab="decided"]').click();
    await loaded;
    const card = await open(page, approval.approve);
    await expect(card.locator("[data-approval-task]")).toHaveText(
      "For task: Send the team note",
    );
    await expect(card.locator("[data-approval-run]")).not.toContainText(
      "not recorded",
    );
    await expect(card.locator("[data-approval-decided]")).toContainText(
      "Approved by you at",
    );
    await expect(card).toContainText(
      /Expires \d.*\((in \d+ (minute|hour|day)s?|in less than a minute|\d+ (minute|hour|day)s? ago|just now|yesterday)\)/,
    );
  });
});

test("a long request is shown whole, and one too long can't be approved", async ({
  page,
}) => {
  await signIn(page, users.owner);
  await page.goto("/approvals");
  // The long requests aren't named by the fixture, so each listed one, in both tabs, is opened in turn.
  let whole = false;
  let refused = false;
  for (const tab of ["waiting", "decided"]) {
    if (tab === "decided") {
      const loaded = page.waitForResponse(
        (reply) =>
          reply.url().includes("/api/v1/approvals?status=decided") &&
          reply.request().method() === "GET",
      );
      await page.locator(`[data-tab="${tab}"]`).click();
      await loaded;
    }
    await expect(page.locator(`[data-tab="${tab}"]`)).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    // A tab shows its loading line until its own list renders, never the other tab's items (WTAP-04),
    // so the items are counted only once it's gone.
    await expect(page.locator('[data-state="loading"]')).toHaveCount(0);
    const items = page.locator("[data-approval-item]");
    for (let index = 0; index < (await items.count()); index += 1) {
      const id = await items.nth(index).getAttribute("data-approval-item");
      await items.nth(index).click();
      const detail = page.locator(`[data-approval="${id}"]`);
      await expect(detail).toBeVisible();
      if (
        (await detail
          .locator("pre")
          .getByText(/CONSEQUENTIAL-TAIL/)
          .count()) > 0
      )
        whole = true;
      if (
        (await detail
          .getByRole("alert")
          .filter({ hasText: "too long to show whole" })
          .count()) > 0
      ) {
        refused = true;
      }
    }
  }
  expect(whole, "a long request's tail is shown").toBe(true);
  expect(refused, "a request too long to show whole is marked").toBe(true);
});

// US-15.5: the inbox, its facts and views, the two-press shortcuts and the sidebar badge.
test("Waiting and Decided tabs with counts, J and K, and the badge", async ({
  page,
}) => {
  await signIn(page, users.owner);
  const counted = await getJson(page, {
    path: "/api/v1/approvals/count",
    parse: parsePendingApprovals,
  });
  const badge = page.locator("[data-approvals-badge]");
  await expect(badge).toHaveText(`${counted.pending} waiting`);
  await expect(
    page.getByRole("link", { name: `Approvals ${counted.pending} waiting` }),
  ).toBeVisible();

  await page.goto("/approvals");
  const waiting = await approvals(page);
  expect(waiting.counts.waiting).toBe(counted.pending);
  await expect(page.locator('[data-tab="waiting"]')).toHaveText(
    `Waiting ${waiting.counts.waiting}`,
  );
  await expect(page.locator('[data-tab="decided"]')).toHaveText(
    `Decided ${waiting.counts.decided}`,
  );
  const items = page.locator("[data-approval-item]");
  await expect(items).toHaveCount(waiting.approvals.length);
  await expect(items.first()).toHaveAttribute("aria-current", "true");
  await expect(page.locator("[data-approval]")).toBeVisible();
  await page.locator("h1").click();
  await page.keyboard.press("j");
  await expect(items.nth(1)).toHaveAttribute("aria-current", "true");
  await page.keyboard.press("k");
  await expect(items.first()).toHaveAttribute("aria-current", "true");
  const loadedDecided = page.waitForResponse((reply) =>
    reply.url().includes("/api/v1/approvals?status=decided"),
  );
  await page.locator('[data-tab="decided"]').click();
  await loadedDecided;
  const decided = await approvals(page, "?status=decided");
  await expect(items).toHaveCount(decided.approvals.length);
  for (const item of decided.approvals)
    expect(["approved", "rejected", "expired", "withdrawn"]).toContain(
      item.status,
    );
});

test("the exact request whole, in Fields and JSON views", async ({ page }) => {
  await signIn(page, users.owner);
  await page.goto("/approvals");
  const card = await open(page, approval.markdown);
  const shown = await listed(page, approval.markdown);
  await expect(card.locator("[data-approval-digest]")).toContainText(
    `sha256 ${shown.argument_hash.slice(0, 8)}`,
  );
  await expect(card.locator("[data-approval-digest]")).toContainText(
    `${shown.arguments_bytes.toLocaleString("en-US")} bytes`,
  );
  await expect(card.locator("pre")).toHaveText(shown.arguments);
  await card.getByRole("button", { name: "Fields" }).click();
  const fields = card.locator("[data-approval-fields]");
  await expect(fields.locator("dt")).toHaveText(["to", "body"]);
  await expect(fields.locator("pre").nth(1)).toHaveText(
    "**Totals** for `Q3`:\n\n- one item\n- two items",
  );
  const rendered = fields.locator("[data-approval-rendered]");
  await expect(rendered.locator("strong")).toHaveText("Totals");
  await expect(rendered.locator("code")).toHaveText("Q3");
  await expect(rendered.locator("li")).toHaveText(["one item", "two items"]);
  await expectNoA11yViolations(page);
  await card.getByRole("button", { name: "JSON" }).click();
  await expect(card.locator("pre")).toHaveText(shown.arguments);
});

test("a shortcut needs a second press, and never acts while typing", async ({
  page,
}) => {
  await signIn(page, users.owner);
  await page.goto("/approvals");
  await open(page, approval.markdown);
  const said = page.locator('[data-message="shortcut"]');
  await page.locator("h1").click();
  await page.keyboard.press("Meta+Enter");
  await expect(said).toContainText("again within 2 seconds to approve");
  // The arm lapses after 2 seconds on its own, which this waits for.
  await expect(said).toHaveText("Nothing was decided.");
  const pending = async () =>
    (await approvals(page)).approvals.some(
      (item) => item.id === approval.markdown,
    );
  expect(await pending()).toBe(true);

  await page.evaluate(() => {
    const field = document.createElement("input");
    field.id = "arranged-field";
    field.setAttribute("aria-label", "Arranged field");
    document.querySelector("main")?.appendChild(field);
    field.focus();
  });
  await page.keyboard.press("Meta+Backspace");
  await page.keyboard.press("Meta+Backspace");
  await expect(said).not.toContainText("again within");
  expect(await pending()).toBe(true);
  await page.evaluate(() =>
    document.getElementById("arranged-field")?.remove(),
  );

  // WTAP-02: a held ⌘↵ repeats its keydown, and an Alt chord isn't the shortcut. Neither decides.
  await page.locator("h1").click();
  await page.keyboard.down("Meta");
  await page.keyboard.down("Enter");
  await expect(said).toContainText("again within 2 seconds to approve");
  await page.keyboard.down("Enter");
  await page.keyboard.up("Enter");
  await page.keyboard.up("Meta");
  await page.keyboard.press("Alt+Enter");
  await page.keyboard.press("Alt+Enter");
  // A decision clears this announcement at once, so still arming, or lapsed, means none was made.
  await page.waitForTimeout(500);
  await expect(said).toHaveText(
    /again within 2 seconds to approve|Nothing was decided\./,
  );
  await expect(page.locator('[data-message="decision"]')).toHaveCount(0);
  expect(await pending()).toBe(true);

  await page.locator("h1").click();
  await page.keyboard.press("Meta+Backspace");
  await expect(said).toContainText("again within 2 seconds to reject");
  await page.keyboard.press("Meta+Backspace");
  await expect(page.locator('[data-message="decision"]')).toContainText(
    "Rejected.",
  );
  expect(await pending()).toBe(false);
  const rejected = await approvals(page, "?status=rejected");
  expect(rejected.approvals.map((item) => item.id)).toContain(
    approval.markdown,
  );
});

// Decision 0027 D2: a decision whose reply is lost stays held, so the other one sends nothing.
// The route answers for the API, so the arranged request is never decided.
test("after a lost Approve, Reject sends nothing and says the first choice may be recorded", async ({
  page,
}) => {
  await signIn(page, users.owner);
  await page.goto("/approvals");
  const sent: { decision: string; key: string }[] = [];
  await page.route(
    `**/api/v1/approvals/${approval.loud}/decision`,
    async (route) => {
      sent.push({
        decision: route.request().postDataJSON().decision,
        key: route.request().headers()["idempotency-key"] ?? "",
      });
      await route.abort("connectionreset");
    },
  );
  const card = await open(page, approval.loud);
  const said = page.locator('[data-message="decision"]');
  await card.getByRole("button", { name: "Approve" }).click();
  await expect(said).toContainText("may have been decided");
  await card.getByRole("button", { name: "Reject" }).click();
  await expect(said).toContainText(
    'Nothing was sent. Your first choice, "Approve"',
  );
  await expect(said).toContainText(
    "Reload to see it before choosing differently.",
  );
  expect(sent.map((item) => item.decision)).toEqual(["approve"]);
  expect(sent[0]?.key).not.toBe("");
  // The same choice again resends the held request, under its key.
  await card.getByRole("button", { name: "Approve" }).click();
  await expect(said).toContainText("may have been decided");
  expect(sent).toHaveLength(2);
  expect(sent[1]).toEqual(sent[0]);
  await page.unroute(`**/api/v1/approvals/${approval.loud}/decision`);
  const waiting = await approvals(page);
  expect(waiting.approvals.some((item) => item.id === approval.loud)).toBe(
    true,
  );
});

// WTAP-05: a failed read says why under the tabs, and only an outage offers Retry. The replies are
// arranged with page.route on the Waiting read.
test("a failed load says why, keeps the tabs, and Retry reads it again", async ({
  page,
}) => {
  await signIn(page, users.owner);
  let arranged: Parameters<Route["fulfill"]>[0] | null = {
    status: 503,
    json: {
      code: "service_unavailable",
      message: "The local API is unavailable.",
    },
  };
  await page.route("**/api/v1/approvals", (route) =>
    arranged === null || route.request().method() !== "GET"
      ? route.continue()
      : route.fulfill(arranged),
  );
  await page.goto("/approvals");
  const state = page.locator('[data-state="unavailable"]');
  await expect(state).toHaveAttribute("data-reason", "unavailable");
  await expect(state.getByRole("alert")).toHaveText(
    "Approvals can't be read right now. Check that the local services are running, then try again.",
  );
  await expect(page.locator('[data-tab="waiting"]')).toBeVisible();
  await expect(page.locator('[data-tab="decided"]')).toBeVisible();
  arranged = null;
  await state.getByRole("button", { name: "Retry" }).click();
  await expect(state).toHaveCount(0);
  const waiting = await approvals(page);
  await expect(page.locator('[data-tab="waiting"]')).toHaveText(
    `Waiting ${waiting.counts.waiting}`,
  );
  await expect(page.locator("[data-approval-item]")).toHaveCount(
    waiting.approvals.length,
  );

  // A signed-out read links to Sign in instead of offering Retry.
  arranged = {
    status: 401,
    json: { code: "not_signed_in", message: "Sign in first." },
  };
  await page.goto("/approvals");
  await expect(state).toHaveAttribute("data-reason", "signed_out");
  await expect(state.getByRole("button", { name: "Retry" })).toHaveCount(0);
  await expect(state.getByRole("link", { name: "Sign in" })).toHaveAttribute(
    "href",
    "/sign-in",
  );
  await page.unroute("**/api/v1/approvals");
});

// WTAP-04: a decision that settles after a switch to Decided reloads Decided, so no waiting request
// is listed under it. The route answers for the API, so the arranged request is never decided.
test("a decision that settles under Decided reloads Decided, never Waiting", async ({
  page,
}) => {
  await signIn(page, users.owner);
  await page.goto("/approvals");
  let release = () => {};
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  const reads: string[] = [];
  page.on("request", (request) => {
    if (
      request.method() === "GET" &&
      /\/api\/v1\/approvals(\?|$)/.test(request.url())
    )
      reads.push(new URL(request.url()).search);
  });
  await page.route(
    `**/api/v1/approvals/${approval.loud}/decision`,
    async (route) => {
      await held;
      await route.fulfill({
        status: 200,
        json: {
          approval_id: approval.loud,
          replayed: false,
          schema_version: 1,
          status: "approved",
        },
      });
    },
  );
  const card = await open(page, approval.loud);
  await card.getByRole("button", { name: "Approve" }).click();
  const loaded = page.waitForResponse((reply) =>
    reply.url().includes("/api/v1/approvals?status=decided"),
  );
  await page.locator('[data-tab="decided"]').click();
  await loaded;
  reads.length = 0;
  const reloaded = page.waitForResponse((reply) =>
    reply.url().includes("/api/v1/approvals?status=decided"),
  );
  release();
  await expect(page.locator('[data-message="decision"]')).toContainText(
    "Only this exact request",
  );
  await reloaded;
  expect(reads).toEqual(["?status=decided"]);
  const decided = await approvals(page, "?status=decided");
  const list = page.getByRole("list", { name: "Decided requests" });
  await expect(list.locator("[data-approval-item]")).toHaveCount(
    decided.approvals.length,
  );
  await expect(list).not.toContainText("Expires");
  await expect(
    page.locator(`[data-approval-item="${approval.loud}"]`),
  ).toHaveCount(0);
  await page.unroute(`**/api/v1/approvals/${approval.loud}/decision`);
  expect(
    (await approvals(page)).approvals.some((item) => item.id === approval.loud),
  ).toBe(true);
});
