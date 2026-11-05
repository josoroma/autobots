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

test("the inbox shows the exact request, and a tampered decision releases nothing", async ({
  page,
}) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
  await page.goto("/approvals");
  const card = page.locator(`[data-approval="${APPROVE}"]`);
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
  await page
    .locator(`[data-approval="${APPROVE}"]`)
    .getByRole("button", { name: "Approve" })
    .click();
  await expect(page.locator('[data-message="decision"]')).toContainText(
    "Only this exact request",
  );
  await expect(page.locator(`[data-approval="${APPROVE}"]`)).toHaveCount(0);
  await page
    .locator(`[data-approval="${REJECT}"]`)
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
