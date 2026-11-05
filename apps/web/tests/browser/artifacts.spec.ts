import { expect, test, type Page } from "@playwright/test";

const EMAIL_A = process.env.AUTOBOTS_TEST_OWNER_EMAIL ?? "";
const PASSWORD_A = process.env.AUTOBOTS_TEST_OWNER_PASSWORD ?? "";
const EMAIL_B = process.env.AUTOBOTS_TEST_OWNER_B_EMAIL ?? "";
const PASSWORD_B = process.env.AUTOBOTS_TEST_OWNER_B_PASSWORD ?? "";
const RUN = process.env.AUTOBOTS_TEST_ARTIFACT_RUN ?? "";
const ARTIFACT = process.env.AUTOBOTS_TEST_ARTIFACT_ID ?? "";
const TEXT = process.env.AUTOBOTS_TEST_ARTIFACT_TEXT ?? "";
const GONE = process.env.AUTOBOTS_TEST_ARTIFACT_GONE ?? "";
const TAMPERED = process.env.AUTOBOTS_TEST_ARTIFACT_TAMPERED ?? "";

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

test("a member lists a run's artifacts and downloads the verified bytes", async ({
  page,
}) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
  const listed = await (
    await page.request.get(`/api/v1/runs/${RUN}/artifacts`)
  ).json();
  expect(listed.artifacts).toHaveLength(1);
  expect(listed.artifacts[0].id).toBe(ARTIFACT);
  expect(listed.artifacts[0].status).toBe("published");
  expect(JSON.stringify(listed)).not.toContain("object_path");
  const download = await page.request.get(
    `/api/v1/artifacts/${ARTIFACT}/download`,
  );
  expect(download.status()).toBe(200);
  expect(await download.text()).toBe(TEXT);
  expect(download.headers()["content-disposition"]).toContain("attachment");
  expect(download.headers()["x-content-type-options"]).toBe("nosniff");
  expect(download.headers()["cache-control"]).toContain("no-store");
});

test("another workspace sees nothing and downloads nothing", async ({
  page,
}) => {
  await signIn(page, EMAIL_B, PASSWORD_B);
  const listed = await (
    await page.request.get(`/api/v1/runs/${RUN}/artifacts`)
  ).json();
  expect(listed.artifacts).toEqual([]);
  const download = await page.request.get(
    `/api/v1/artifacts/${ARTIFACT}/download`,
  );
  expect(download.status()).toBe(404);
  expect(await download.text()).not.toContain(TEXT);
});

test("a missing or altered object is reported and never served", async ({
  page,
}) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
  for (const id of [GONE, TAMPERED]) {
    const download = await page.request.get(`/api/v1/artifacts/${id}/download`);
    expect(download.status()).toBe(409);
    expect((await download.json()).code).toBe("artifact_missing");
  }
});

test("a signed-out request gets no bytes", async ({ request }) => {
  const download = await request.get(`/api/v1/artifacts/${ARTIFACT}/download`);
  expect(download.status()).toBe(401);
  expect(await download.text()).not.toContain(TEXT);
});
