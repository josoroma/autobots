import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const EMAIL_A = process.env.AUTOBOTS_TEST_OWNER_EMAIL ?? "";
const PASSWORD_A = process.env.AUTOBOTS_TEST_OWNER_PASSWORD ?? "";
const EMAIL_B = process.env.AUTOBOTS_TEST_OWNER_B_EMAIL ?? "";
const PASSWORD_B = process.env.AUTOBOTS_TEST_OWNER_B_PASSWORD ?? "";
const EMAIL_C = process.env.AUTOBOTS_TEST_MEMBER_EMAIL ?? "";
const PASSWORD_C = process.env.AUTOBOTS_TEST_MEMBER_PASSWORD ?? "";
const APPROVE = process.env.AUTOBOTS_TEST_APPROVAL_APPROVE ?? "";
const REJECT = process.env.AUTOBOTS_TEST_APPROVAL_REJECT ?? "";
const HASH = process.env.AUTOBOTS_TEST_APPROVAL_HASH ?? "";
const RUN = process.env.AUTOBOTS_TEST_APPROVAL_RUN ?? "";
const LEGACY = process.env.AUTOBOTS_TEST_APPROVAL_LEGACY ?? "";
const LEGACY_HASH = process.env.AUTOBOTS_TEST_APPROVAL_LEGACY_HASH ?? "";
const LEGACY_RUN = process.env.AUTOBOTS_TEST_APPROVAL_LEGACY_RUN ?? "";
const LOUD = process.env.AUTOBOTS_TEST_APPROVAL_LOUD ?? "";
const MARKDOWN = process.env.AUTOBOTS_TEST_APPROVAL_MARKDOWN ?? "";
const EXPERT = process.env.AUTOBOTS_TEST_APPROVAL_EXPERT ?? "";
const POLICY_REASON =
  "This tool changes something outside this Mac, so policy holds each call for a person.";

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

// US-15.5: the inbox lists requests beside the selected one's detail, so a test selects it first.
async function open(page: Page, id: string) {
  await page.locator(`[data-approval-item="${id}"]`).click();
  const card = page.locator(`[data-approval="${id}"]`);
  await expect(card).toBeVisible();
  return card;
}

async function write(page: Page, key: string): Promise<Record<string, string>> {
  const token = await (await page.request.get("/api/csrf")).json();
  return {
    [token.header]: token.token,
    Origin: new URL(page.url()).origin,
    "Content-Type": "application/json",
    "Idempotency-Key": key,
  };
}

test("another workspace and a member can't decide", async ({ browser }) => {
  const other = await (await browser.newContext()).newPage();
  await signIn(other, EMAIL_B, PASSWORD_B);
  const list = await (await other.request.get("/api/v1/approvals")).json();
  expect(list.approvals.map((item: { id: string }) => item.id)).not.toContain(
    APPROVE,
  );
  const foreign = await other.request.post(
    `/api/v1/approvals/${APPROVE}/decision`,
    {
      headers: await write(other, "foreign"),
      data: { decision: "approve", argument_hash: HASH },
    },
  );
  expect(foreign.status()).toBe(404);
  const member = await (await browser.newContext()).newPage();
  await signIn(member, EMAIL_C, PASSWORD_C);
  const denied = await member.request.post(
    `/api/v1/approvals/${APPROVE}/decision`,
    {
      headers: await write(member, "member"),
      data: { decision: "approve", argument_hash: HASH },
    },
  );
  expect(denied.status()).toBe(403);
});

test("each request shows the policy's reason, its target, the exact action and its expiry", async ({
  page,
}) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
  await page.goto("/approvals");
  const card = await open(page, APPROVE);
  await expect(card.locator("[data-approval-reason]")).toHaveText(
    `Why it's asking: ${POLICY_REASON}`,
  );
  await expect(card.locator("[data-approval-target]")).toHaveText(
    "Target: Mail to team@example.invalid",
  );
  await expect(card.locator("pre")).toContainText('"body": "hello"');
  await expect(card).toContainText(/Expires \d/);

  // What the model wrote stays in the request, and doesn't reach the reason.
  const loud = await open(page, LOUD);
  await expect(loud.locator("pre")).toContainText("REASON FROM THE MODEL");
  await expect(loud.locator("[data-approval-reason]")).toHaveText(
    `Why it's asking: ${POLICY_REASON}`,
  );
});

test("each request shows who asked, its scope and its policy version, as stored with it", async ({
  page,
}) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
  await page.goto("/approvals");
  const card = await open(page, APPROVE);
  await expect(card.locator("[data-approval-requester]")).toHaveText(
    'Requested by: you started this run, and Expert "Mail sender", version 2, proposed it.',
  );
  await expect(card.locator("[data-approval-scope]")).toContainText(
    "Scope when asked: tools mock_send version 1",
  );
  await expect(card.locator("[data-approval-policy]")).toHaveText(
    "Policy version: approval-policy/2, rule consequential external write.",
  );
  const listed = await (await page.request.get("/api/v1/approvals")).json();
  const shown = listed.approvals.find(
    (item: { id: string }) => item.id === APPROVE,
  );
  expect(shown.argument_hash).toBe(HASH);
  expect(shown.requester).toMatchObject({
    person_is_viewer: true,
    agent: "expert",
    expert_id: EXPERT,
    expert_version: 2,
  });
  expect(shown.scope_snapshot.tools.mock_send).toBe(1);
  // Another run in this workspace, with no Expert, names the coordinator.
  const other = await open(page, REJECT);
  await expect(other.locator("[data-approval-requester]")).toContainText(
    "the coordinator proposed it",
  );
});

test("a request saved before these fields says so, and its decision stays bound to the hash shown", async ({
  page,
}) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
  await page.goto("/approvals");
  const card = await open(page, LEGACY);
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
    `/api/v1/approvals/${LEGACY}/decision`,
    {
      headers: await write(page, "legacy-tamper"),
      data: { decision: "approve", argument_hash: "0".repeat(64) },
    },
  );
  expect(tampered.status()).toBe(409);
  expect((await tampered.json()).code).toBe("approval_mismatch");
  const listed = await (await page.request.get("/api/v1/approvals")).json();
  const shown = listed.approvals.find(
    (item: { id: string }) => item.id === LEGACY,
  );
  expect(shown.argument_hash).toBe(LEGACY_HASH);
  await card.getByRole("button", { name: "Reject" }).click();
  await expect(page.locator('[data-message="decision"]')).toContainText(
    "Rejected.",
  );
  const summary = await (
    await page.request.get(`/api/v1/runs/${LEGACY_RUN}`)
  ).json();
  expect(summary.status).not.toBe("waiting_approval");
});

test("the inbox shows the exact request, and a tampered decision releases nothing", async ({
  page,
}) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
  await page.goto("/approvals");
  const card = await open(page, APPROVE);
  await expect(card).toContainText("mock_send, version 1");
  await expect(card).toContainText("team@example.invalid");
  await expect(card).toContainText("consequential external write");
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(results.violations.map((violation) => violation.id)).toEqual([]);

  const tampered = await page.request.post(
    `/api/v1/approvals/${APPROVE}/decision`,
    {
      headers: await write(page, "tamper"),
      data: { decision: "approve", argument_hash: "0".repeat(64) },
    },
  );
  expect(tampered.status()).toBe(409);
  expect((await tampered.json()).code).toBe("approval_mismatch");
  const summary = await (await page.request.get(`/api/v1/runs/${RUN}`)).json();
  expect(summary.status).toBe("waiting_approval");
});

test("an owner approves and rejects through the inbox, and a repeat changes nothing", async ({
  page,
}) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
  await page.goto("/approvals");
  await (
    await open(page, APPROVE)
  )
    .getByRole("button", { name: "Approve" })
    .click();
  await expect(page.locator('[data-message="decision"]')).toContainText(
    "Only this exact request",
  );
  await expect(page.locator(`[data-approval="${APPROVE}"]`)).toHaveCount(0);
  await (
    await open(page, REJECT)
  )
    .getByRole("button", { name: "Reject" })
    .click();
  await expect(page.locator('[data-message="decision"]')).toContainText(
    "won't run",
  );

  const summary = await (await page.request.get(`/api/v1/runs/${RUN}`)).json();
  expect(summary.status).toBe("queued");
  const again = await page.request.post(
    `/api/v1/approvals/${APPROVE}/decision`,
    {
      headers: await write(page, "again"),
      data: { decision: "approve", argument_hash: HASH },
    },
  );
  expect((await again.json()).replayed).toBe(true);
  const opposite = await page.request.post(
    `/api/v1/approvals/${APPROVE}/decision`,
    {
      headers: await write(page, "opposite"),
      data: { decision: "reject", argument_hash: HASH },
    },
  );
  expect(opposite.status()).toBe(409);
  expect((await opposite.json()).code).toBe("approval_already_decided");
  const history = await (
    await page.request.get("/api/v1/approvals?status=approved")
  ).json();
  expect(history.approvals.map((item: { id: string }) => item.id)).toContain(
    APPROVE,
  );
});

test("a long request is shown whole, and one too long can't be approved", async ({
  page,
}) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
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
  await signIn(page, EMAIL_A, PASSWORD_A);
  const counted = await (
    await page.request.get("/api/v1/approvals/count")
  ).json();
  const badge = page.locator("[data-approvals-badge]");
  await expect(badge).toHaveText(`${counted.pending} waiting`);
  await expect(
    page.getByRole("link", { name: `Approvals ${counted.pending} waiting` }),
  ).toBeVisible();

  await page.goto("/approvals");
  const waiting = await (await page.request.get("/api/v1/approvals")).json();
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
  const decided = await (
    await page.request.get("/api/v1/approvals?status=decided")
  ).json();
  await expect(items).toHaveCount(decided.approvals.length);
  for (const item of decided.approvals as { status: string }[])
    expect(["approved", "rejected", "expired", "withdrawn"]).toContain(
      item.status,
    );
});

test("a decided request shows its run, task, expiry and who decided", async ({
  page,
}) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
  await page.goto("/approvals");
  const loaded = page.waitForResponse((reply) =>
    reply.url().includes("/api/v1/approvals?status=decided"),
  );
  await page.locator('[data-tab="decided"]').click();
  await loaded;
  const card = await open(page, APPROVE);
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
    /Expires \d.*\((in \d|in less than a minute|\d+ (minute|hour|day)s? ago|just now|yesterday)\)/,
  );
});

test("the exact request whole, in Fields and JSON views", async ({ page }) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
  await page.goto("/approvals");
  const card = await open(page, MARKDOWN);
  const listed = (
    await (await page.request.get("/api/v1/approvals")).json()
  ).approvals.find((item: { id: string }) => item.id === MARKDOWN);
  await expect(card.locator("[data-approval-digest]")).toContainText(
    `sha256 ${listed.argument_hash.slice(0, 8)}`,
  );
  await expect(card.locator("[data-approval-digest]")).toContainText(
    `${listed.arguments_bytes.toLocaleString("en-US")} bytes`,
  );
  await expect(card.locator("pre")).toHaveText(listed.arguments);
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
  const axe = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(axe.violations.map((item) => item.id)).toEqual([]);
  await card.getByRole("button", { name: "JSON" }).click();
  await expect(card.locator("pre")).toHaveText(listed.arguments);
});

test("a shortcut needs a second press, and never acts while typing", async ({
  page,
}) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
  await page.goto("/approvals");
  await open(page, MARKDOWN);
  const said = page.locator('[data-message="shortcut"]');
  await page.locator("h1").click();
  await page.keyboard.press("Meta+Enter");
  await expect(said).toContainText("again within 2 seconds to approve");
  await page.waitForTimeout(2_500);
  await expect(said).toHaveText("Nothing was decided.");
  const pending = async () =>
    (
      (await (await page.request.get("/api/v1/approvals")).json())
        .approvals as { id: string }[]
    ).some((item) => item.id === MARKDOWN);
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
  const rejected = await (
    await page.request.get("/api/v1/approvals?status=rejected")
  ).json();
  expect(rejected.approvals.map((item: { id: string }) => item.id)).toContain(
    MARKDOWN,
  );
});

// Decision 0027 D2: a decision whose reply is lost stays held, so the other one sends nothing.
// The route answers for the API, so the arranged request is never decided.
test("after a lost Approve, Reject sends nothing and says the first choice may be recorded", async ({
  page,
}) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
  await page.goto("/approvals");
  const sent: { decision: string; key: string }[] = [];
  await page.route(`**/api/v1/approvals/${LOUD}/decision`, async (route) => {
    sent.push({
      decision: route.request().postDataJSON().decision,
      key: route.request().headers()["idempotency-key"] ?? "",
    });
    await route.abort("connectionreset");
  });
  const card = await open(page, LOUD);
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
  await page.unroute(`**/api/v1/approvals/${LOUD}/decision`);
  const listed = await (await page.request.get("/api/v1/approvals")).json();
  expect(
    listed.approvals.some((item: { id: string }) => item.id === LOUD),
  ).toBe(true);
});
