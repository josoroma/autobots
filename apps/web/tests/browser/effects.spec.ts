import { expect, test, type Page } from "@playwright/test";

const EMAIL_A = process.env.AUTOBOTS_TEST_OWNER_EMAIL ?? "";
const PASSWORD_A = process.env.AUTOBOTS_TEST_OWNER_PASSWORD ?? "";
const EMAIL_B = process.env.AUTOBOTS_TEST_OWNER_B_EMAIL ?? "";
const PASSWORD_B = process.env.AUTOBOTS_TEST_OWNER_B_PASSWORD ?? "";
const EMAIL_C = process.env.AUTOBOTS_TEST_MEMBER_EMAIL ?? "";
const PASSWORD_C = process.env.AUTOBOTS_TEST_MEMBER_PASSWORD ?? "";
const RUN = process.env.AUTOBOTS_TEST_UNKNOWN_RUN ?? "";
const OPERATION = process.env.AUTOBOTS_TEST_UNKNOWN_OPERATION ?? "";

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

test("an unknown effect is visible, blocks resume, and only an owner can resolve it", async ({
  browser,
}) => {
  const other = await (await browser.newContext()).newPage();
  await signIn(other, EMAIL_B, PASSWORD_B);
  const foreign = await other.request.post(
    `/api/v1/runs/${RUN}/effects/${OPERATION}/reconcile`,
    {
      headers: await write(other, "foreign"),
      data: { outcome: "delivered", evidence: "x", generation: 1 },
    },
  );
  expect(foreign.status()).toBe(404);
  const member = await (await browser.newContext()).newPage();
  await signIn(member, EMAIL_C, PASSWORD_C);
  const denied = await member.request.post(
    `/api/v1/runs/${RUN}/effects/${OPERATION}/reconcile`,
    {
      headers: await write(member, "member"),
      data: { outcome: "delivered", evidence: "x", generation: 1 },
    },
  );
  expect(denied.status()).toBe(403);

  const page = await (await browser.newContext()).newPage();
  await signIn(page, EMAIL_A, PASSWORD_A);
  await page.goto(`/runs/${RUN}`);
  await expect(page.locator("[data-run-status]")).toHaveAttribute(
    "data-run-status",
    "paused",
  );
  await expect(page.locator("[data-stop-reason]")).toContainText(
    "outcome unknown",
  );
  const panel = page.locator("[data-unknown-effects]");
  await expect(panel).toContainText("send_blind");
  await expect(panel).toContainText("may or may not have happened");
  await expect(
    panel.getByRole("button", { name: "It happened" }),
  ).toBeDisabled();

  const version = (await (await page.request.get(`/api/v1/runs/${RUN}`)).json())
    .version;
  const early = await page.request.post(`/api/v1/runs/${RUN}/resume`, {
    headers: await write(page, "early"),
    data: { expected_version: version },
  });
  expect(early.status()).toBe(409);
  expect(["unknown_effect", "credentials_required"]).toContain(
    (await early.json()).code,
  );

  await page.getByLabel("What you saw").fill("Seen in the destination log.");
  await panel.getByRole("button", { name: "It happened" }).click();
  await expect(page.locator("[data-unknown-effects]")).toHaveCount(0);
  await expect(
    page.locator("[data-sequence]").filter({ hasText: "reconciled" }),
  ).toHaveCount(1);
  const again = await page.request.post(
    `/api/v1/runs/${RUN}/effects/${OPERATION}/reconcile`,
    {
      headers: await write(page, "again"),
      data: { outcome: "not_delivered", evidence: "changed", generation: 1 },
    },
  );
  expect(again.status()).toBe(409);
  expect((await again.json()).code).toBe("operation_not_unknown");
});
