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

test("a workflow's optional description and step labels, edited in the editor and read through the BFF", async ({
  page,
}) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
  await page.goto("/workflows");
  const stamp = Date.now();
  const created = await page.request.post("/api/v1/workflows", {
    headers: await write(page, `described-${stamp}`),
    data: { name: `Described ${stamp}`, description: "Shouts the topic back" },
  });
  expect(created.status()).toBe(201);
  const described = await created.json();
  const plain = await (
    await page.request.post("/api/v1/workflows", {
      headers: await write(page, `plain-${stamp}`),
      data: { name: `Plain ${stamp}` },
    })
  ).json();
  const read = async (id: string) =>
    (await page.request.get(`/api/v1/workflows/${id}`)).json();
  expect((await read(described.id)).description).toBe("Shouts the topic back");
  expect((await read(plain.id)).description).toBeNull();

  // The description is edited in the editor, and changes no version.
  await page.goto(`/workflows/${plain.id}`);
  await page.getByLabel("Description").fill("Added in the editor");
  await page.getByRole("button", { name: "Save description" }).click();
  await expect(page.locator('[data-message="editor"]')).toHaveText(
    "Description saved. No version changed.",
  );
  await page.reload();
  await expect(page.getByLabel("Description")).toHaveValue(
    "Added in the editor",
  );
  expect((await read(plain.id)).latest_version).toBe(0);

  // A label bumps the graph to IR version 2, and it publishes with the label.
  await page.goto(`/workflows/${described.id}`);
  await page.getByLabel("Graph").fill(JSON.stringify(GRAPH));
  await page.getByLabel("up (transform)").fill("Shout it");
  const draft = JSON.parse(await page.getByLabel("Graph").inputValue());
  expect(draft.ir_version).toBe(2);
  expect(draft.nodes[1].label).toBe("Shout it");
  await page.getByRole("button", { name: "Validate" }).click();
  await expect(page.locator('[data-validation="valid"]')).toBeVisible();
  await page.getByRole("button", { name: "Publish", exact: true }).click();
  await expect(page.locator('[data-message="editor"]')).toContainText(
    "Published as version 1",
  );
  const published = (await read(described.id)).versions[0];
  expect(published.graph.ir_version).toBe(2);
  expect(
    published.graph.nodes.map((node: { label: string | null }) => node.label),
  ).toEqual([null, "Shout it", null]);
  // Clearing the only label returns the draft to IR version 1.
  await page.getByLabel("up (transform)").fill("");
  expect(
    JSON.parse(await page.getByLabel("Graph").inputValue()).ir_version,
  ).toBeUndefined();

  // An unlabelled graph still validates and publishes at IR version 1, with the hash it always had.
  const checked = await (
    await page.request.post("/api/v1/workflows/validate", {
      headers: await write(page, `validate-${stamp}`),
      data: GRAPH,
    })
  ).json();
  expect(checked.valid).toBe(true);
  const versioned = await page.request.post(
    `/api/v1/workflows/${plain.id}/versions`,
    {
      headers: await write(page, `publish-${stamp}`),
      data: { expected_version: 0, graph: GRAPH },
    },
  );
  expect(versioned.status()).toBe(201);
  const first = (await versioned.json()).versions[0];
  expect(first.graph.ir_version).toBeNull();
  expect(first.graph_hash).toBe(checked.graph_hash);
});

test("one saved draft: the owner saves it, publishes it under the expected version or discards it, and nothing runs it", async ({
  page,
  browser,
}) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
  await page.goto("/workflows");
  const stamp = Date.now();
  const graph = (operation: string, label?: string) => ({
    ...GRAPH,
    ...(label === undefined ? {} : { ir_version: 2 }),
    nodes: GRAPH.nodes.map((node) =>
      node.id === "up"
        ? {
            ...node,
            config: { operation },
            ...(label === undefined ? {} : { label }),
          }
        : node,
    ),
  });
  const flow = await (
    await page.request.post("/api/v1/workflows", {
      headers: await write(page, `drafted-${stamp}`),
      data: { name: `Drafted ${stamp}` },
    })
  ).json();
  const base = `/api/v1/workflows/${flow.id}`;
  for (const [index, operation] of ["upper", "lower", "to_string"].entries()) {
    const published = await page.request.post(`${base}/versions`, {
      headers: await write(page, `drafted-${stamp}-${index}`),
      data: { expected_version: index, graph: graph(operation) },
    });
    expect(published.status()).toBe(201);
  }
  const read = async () => (await page.request.get(base)).json();
  const hashes = (await read()).versions.map(
    (item: { version: number; graph_hash: string }) =>
      `${item.version}:${item.graph_hash}`,
  );
  expect(hashes).toHaveLength(3);

  // Saved twice from the editor: one draft, the second graph.
  await page.goto(`/workflows/${flow.id}`);
  await page.getByLabel("Graph").fill(JSON.stringify(graph("lower")));
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.locator('[data-message="editor"]')).toHaveText(
    "Draft saved. Runs keep using the published versions.",
  );
  await page
    .getByLabel("Graph")
    .fill(JSON.stringify(graph("upper", "Second draft")));
  const saved = page.waitForResponse(
    (reply) =>
      reply.url().endsWith(`/workflows/${flow.id}/draft`) &&
      reply.request().method() === "PUT",
  );
  await page.getByRole("button", { name: "Save draft" }).click();
  expect((await saved).status()).toBe(200);
  await expect(page.locator('[data-field="draft-badge"]')).toBeVisible();
  const second = (await read()).draft;
  expect(second.graph.ir_version).toBe(2);
  expect(second.graph.nodes[1].label).toBe("Second draft");

  // A member who isn't the owner can't save one.
  const context = await browser.newContext();
  const member = await context.newPage();
  await signIn(member, EMAIL_C, PASSWORD_C);
  const refused = await member.request.put(`${base}/draft`, {
    headers: {
      ...(await write(member, `member-${stamp}`)),
      "X-Autobots-Workspace": process.env.AUTOBOTS_TEST_WORKSPACE_A ?? "",
    },
    data: { graph: graph("lower") },
  });
  expect(refused.status()).toBe(403);
  expect((await refused.json()).code).toBe("owner_required");
  await context.close();
  expect((await read()).draft.graph).toEqual(second.graph);

  // A stale publish creates nothing and keeps the draft.
  const stale = await page.request.post(`${base}/draft/publish`, {
    headers: await write(page, `stale-${stamp}`),
    data: { expected_version: 2 },
  });
  expect(stale.status()).toBe(409);
  expect((await stale.json()).code).toBe("workflow_version_conflict");
  let current = await read();
  expect(current.latest_version).toBe(3);
  expect(current.draft).not.toBeNull();

  // Publishing from the editor names version 3 and creates immutable version 4.
  await page.reload();
  await page.getByRole("button", { name: "Publish draft" }).click();
  await expect(page.locator('[data-message="editor"]')).toHaveText(
    "Published the draft as version 4. Earlier versions don't change.",
  );
  current = await read();
  expect(current.latest_version).toBe(4);
  expect(current.draft).toBeNull();
  expect(current.versions[3].graph.nodes[1].label).toBe("Second draft");
  const fourth = current.versions[3].graph_hash;

  // Runs and routines can't name a draft. An execution binds a published version's hash.
  await page.request.put(`${base}/draft`, {
    headers: await write(page, `again-${stamp}`),
    data: { graph: graph("lower") },
  });
  const draftRun = await page.request.post(`${base}/executions`, {
    headers: await write(page, `run-draft-${stamp}`),
    data: { version: "draft", inputs: { in: "x" } },
  });
  expect(draftRun.status()).toBe(409);
  expect((await draftRun.json()).code).toBe("draft_not_runnable");
  const draftRoutine = await page.request.post("/api/v1/routines", {
    headers: await write(page, `routine-draft-${stamp}`),
    data: {
      name: `Draft routine ${stamp}`,
      config: {
        target: { kind: "workflow", id: flow.id, version: "draft" },
        trigger: { kind: "daily", time: "09:00" },
      },
    },
  });
  expect(draftRoutine.status()).toBe(422);
  expect((await draftRoutine.json()).code).toBe("draft_not_runnable");
  const bound = await page.request.post(`${base}/executions`, {
    headers: await write(page, `run-four-${stamp}`),
    data: { version: 4, inputs: { in: "x" } },
  });
  expect(bound.status()).toBe(201);
  const binding = await bound.json();
  expect(binding.workflow_version).toBe(4);
  expect(binding.graph_hash).toBe(fourth);

  // Discarding leaves every published version and its hash alone.
  await page.reload();
  await page.getByRole("button", { name: "Discard draft" }).click();
  await expect(page.locator('[data-message="editor"]')).toHaveText(
    "Draft discarded. The published versions are unchanged.",
  );
  current = await read();
  expect(current.draft).toBeNull();
  expect(
    current.versions
      .slice(0, 3)
      .map(
        (item: { version: number; graph_hash: string }) =>
          `${item.version}:${item.graph_hash}`,
      ),
  ).toEqual(hashes);
  expect(current.versions[3].graph_hash).toBe(fourth);
  await expect(page.locator('[data-field="draft-badge"]')).toHaveCount(0);
});
