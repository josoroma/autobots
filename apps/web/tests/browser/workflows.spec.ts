import { expect, test, type Page } from "@playwright/test";

const EMAIL_A = process.env.AUTOBOTS_TEST_OWNER_EMAIL ?? "";
const PASSWORD_A = process.env.AUTOBOTS_TEST_OWNER_PASSWORD ?? "";
const EMAIL_B = process.env.AUTOBOTS_TEST_OWNER_B_EMAIL ?? "";
const PASSWORD_B = process.env.AUTOBOTS_TEST_OWNER_B_PASSWORD ?? "";
const EMAIL_C = process.env.AUTOBOTS_TEST_MEMBER_EMAIL ?? "";
const PASSWORD_C = process.env.AUTOBOTS_TEST_MEMBER_PASSWORD ?? "";

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

const GRAPH = {
  nodes: [
    { id: "in", block: "input", version: 1, config: { type: "string" } },
    {
      id: "up",
      block: "transform",
      version: 1,
      config: { operation: "upper" },
    },
    { id: "out", block: "output", version: 1 },
  ],
  links: [
    { source: "in", source_port: "value", target: "up", target_port: "value" },
    { source: "up", source_port: "value", target: "out", target_port: "value" },
  ],
};

test("validation returns typed errors, publishing keeps versions, and an execution is bound", async ({
  browser,
}) => {
  const page = await (await browser.newContext()).newPage();
  await signIn(page, EMAIL_A, PASSWORD_A);
  await page.goto("/");
  const cycle = {
    nodes: GRAPH.nodes,
    links: [
      ...GRAPH.links,
      {
        source: "up",
        source_port: "value",
        target: "up",
        target_port: "value",
      },
    ],
  };
  const invalid = await page.request.post("/api/v1/workflows/validate", {
    headers: await write(page, "v1"),
    data: cycle,
  });
  const checked = await invalid.json();
  expect(checked.valid).toBe(false);
  expect(checked.errors[0].code).toBe("input_linked_twice");
  const valid = await (
    await page.request.post("/api/v1/workflows/validate", {
      headers: await write(page, "v2"),
      data: GRAPH,
    })
  ).json();
  expect(valid.valid).toBe(true);
  expect(valid.graph_hash).toHaveLength(64);

  const created = await (
    await page.request.post("/api/v1/workflows", {
      headers: await write(page, "w1"),
      data: { name: "Browser flow" },
    })
  ).json();
  const refused = await page.request.post(
    `/api/v1/workflows/${created.id}/versions`,
    {
      headers: await write(page, "bad"),
      data: { expected_version: 0, graph: cycle },
    },
  );
  expect(refused.status()).toBe(422);
  expect((await refused.json()).code).toBe("workflow_invalid");
  const published = await page.request.post(
    `/api/v1/workflows/${created.id}/versions`,
    {
      headers: await write(page, "p1"),
      data: { expected_version: 0, graph: GRAPH },
    },
  );
  expect(published.status()).toBe(201);
  expect((await published.json()).versions[0].graph_hash).toBe(
    valid.graph_hash,
  );
  const execution = await page.request.post(
    `/api/v1/workflows/${created.id}/executions`,
    {
      headers: await write(page, "e1"),
      data: { version: 1, inputs: { in: "hello" } },
    },
  );
  expect(execution.status()).toBe(201);
  expect((await execution.json()).graph_hash).toBe(valid.graph_hash);

  const other = await (await browser.newContext()).newPage();
  await signIn(other, EMAIL_B, PASSWORD_B);
  expect(
    (await other.request.get(`/api/v1/workflows/${created.id}`)).status(),
  ).toBe(404);
  const member = await (await browser.newContext()).newPage();
  await signIn(member, EMAIL_C, PASSWORD_C);
  const denied = await member.request.post(
    `/api/v1/workflows/${created.id}/versions`,
    {
      headers: await write(member, "m1"),
      data: { expected_version: 1, graph: GRAPH },
    },
  );
  expect(denied.status()).toBe(403);
});
