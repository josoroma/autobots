import {
  parseExecutionBinding,
  parseWorkflowValidation,
  parseWorkflowView,
  type WorkflowGraph,
} from "@autobots/api-client";
import type { Page } from "@playwright/test";

import { expectRefusal, getJson, send, writeHeaders } from "./support/api.ts";
import { signIn, users } from "./support/auth.ts";
import { link, node } from "./support/builders.ts";
import { need } from "./support/env.ts";
import { expect, test } from "./support/fixtures.ts";

const GRAPH = {
  nodes: [
    node("in", "input", { type: "string" }),
    node("up", "transform", { operation: "upper" }),
    node("out", "output"),
  ],
  links: [
    link("in", "value", "up", "value"),
    link("up", "value", "out", "value"),
  ],
};

function createWorkflow(page: Page, key: string, data: object) {
  return send(page, {
    path: "/api/v1/workflows",
    key,
    data,
    status: 201,
    parse: parseWorkflowView,
  });
}

function readWorkflow(page: Page, id: string) {
  return getJson(page, {
    path: `/api/v1/workflows/${id}`,
    parse: parseWorkflowView,
  });
}

function validate(page: Page, key: string, graph: WorkflowGraph) {
  return send(page, {
    path: "/api/v1/workflows/validate",
    key,
    data: graph,
    status: 200,
    parse: parseWorkflowValidation,
  });
}

function publish(
  page: Page,
  id: string,
  {
    key,
    expectedVersion,
    graph,
  }: { key: string; expectedVersion: number; graph: WorkflowGraph },
) {
  return send(page, {
    path: `/api/v1/workflows/${id}/versions`,
    key,
    data: { expected_version: expectedVersion, graph },
    status: 201,
    parse: parseWorkflowView,
  });
}

test("validation returns typed errors, publishing keeps versions, and an execution is bound", async ({
  asOwner: page,
  signedInPage,
}) => {
  await page.goto("/");
  const cycle = {
    nodes: GRAPH.nodes,
    links: [...GRAPH.links, link("up", "value", "up", "value")],
  };
  const checked = await validate(page, "v1", cycle);
  expect(checked.valid).toBe(false);
  expect(checked.errors[0]?.code).toBe("input_linked_twice");
  const valid = await validate(page, "v2", GRAPH);
  expect(valid.valid).toBe(true);
  expect(valid.graph_hash).toHaveLength(64);

  const created = await createWorkflow(page, "w1", { name: "Browser flow" });
  const refused = await page.request.post(
    `/api/v1/workflows/${created.id}/versions`,
    {
      headers: await writeHeaders(page, "bad"),
      data: { expected_version: 0, graph: cycle },
    },
  );
  await expectRefusal(refused, { status: 422, code: "workflow_invalid" });
  const published = await publish(page, created.id, {
    key: "p1",
    expectedVersion: 0,
    graph: GRAPH,
  });
  expect(published.versions[0]?.graph_hash).toBe(valid.graph_hash);
  const execution = await send(page, {
    path: `/api/v1/workflows/${created.id}/executions`,
    key: "e1",
    data: { version: 1, inputs: { in: "hello" } },
    status: 201,
    parse: parseExecutionBinding,
  });
  expect(execution.graph_hash).toBe(valid.graph_hash);

  const other = await signedInPage(users.ownerB);
  expect(
    (await other.request.get(`/api/v1/workflows/${created.id}`)).status(),
  ).toBe(404);
  const member = await signedInPage(users.member);
  const denied = await member.request.post(
    `/api/v1/workflows/${created.id}/versions`,
    {
      headers: await writeHeaders(member, "m1"),
      data: { expected_version: 1, graph: GRAPH },
    },
  );
  expect(denied.status()).toBe(403);
});

test("a workflow's optional description and step labels, edited in the editor and read through the BFF", async ({
  page,
}) => {
  await signIn(page, users.owner);
  await page.goto("/workflows");
  const stamp = Date.now();
  const described = await createWorkflow(page, `described-${stamp}`, {
    name: `Described ${stamp}`,
    description: "Shouts the topic back",
  });
  const plain = await createWorkflow(page, `plain-${stamp}`, {
    name: `Plain ${stamp}`,
  });
  expect((await readWorkflow(page, described.id)).description).toBe(
    "Shouts the topic back",
  );
  expect((await readWorkflow(page, plain.id)).description).toBeNull();

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
  expect((await readWorkflow(page, plain.id)).latest_version).toBe(0);

  // A label bumps the graph to IR version 2, and it publishes with the label.
  await page.goto(`/workflows/${described.id}`);
  await page.getByLabel("Graph").fill(JSON.stringify(GRAPH));
  await page.getByLabel("up (transform)").fill("Shout it");
  const draft = JSON.parse(await page.getByLabel("Graph").inputValue());
  expect(draft.ir_version).toBe(2);
  expect(draft.nodes[1].label).toBe("Shout it");
  await page.getByRole("button", { name: "Validate" }).click();
  await expect(page.locator('[data-validation="valid"]')).toBeVisible();
  await page.getByRole("button", { name: "Publish what is shown" }).click();
  await expect(page.locator('[data-message="editor"]')).toContainText(
    "Published as version 1",
  );
  const published = (await readWorkflow(page, described.id)).versions[0];
  expect(published?.graph.ir_version).toBe(2);
  expect(published?.graph.nodes?.map((item) => item.label)).toEqual([
    null,
    "Shout it",
    null,
  ]);
  // Clearing the only label keeps IR version 2, as the domain's label rule does (Decision 0029 F1).
  await page.getByLabel("up (transform)").fill("");
  const cleared = JSON.parse(await page.getByLabel("Graph").inputValue());
  expect(cleared.ir_version).toBe(2);
  expect(cleared.nodes[1].label).toBeUndefined();

  // An unlabelled graph still validates and publishes at IR version 1, with the hash it always had.
  const checked = await validate(page, `validate-${stamp}`, GRAPH);
  expect(checked.valid).toBe(true);
  const versioned = await publish(page, plain.id, {
    key: `publish-${stamp}`,
    expectedVersion: 0,
    graph: GRAPH,
  });
  const first = versioned.versions[0];
  expect(first?.graph.ir_version).toBeNull();
  expect(first?.graph_hash).toBe(checked.graph_hash);
});

/** The arranged graph with the step `up` doing `operation`, and labelled when `label` is given. */
function graph(operation: string, label?: string): WorkflowGraph {
  return {
    ...GRAPH,
    ...(label === undefined ? {} : { ir_version: 2 }),
    nodes: GRAPH.nodes.map((item) =>
      item.id === "up"
        ? {
            ...item,
            config: { operation },
            ...(label === undefined ? {} : { label }),
          }
        : item,
    ),
  };
}

test("one saved draft: the owner saves it, publishes it under the expected version or discards it, and nothing runs it", async ({
  page,
  signedInPage,
}) => {
  await signIn(page, users.owner);
  await page.goto("/workflows");
  const stamp = Date.now();
  const flow = await createWorkflow(page, `drafted-${stamp}`, {
    name: `Drafted ${stamp}`,
  });
  const base = `/api/v1/workflows/${flow.id}`;
  for (const [index, operation] of ["upper", "lower", "to_string"].entries()) {
    await publish(page, flow.id, {
      key: `drafted-${stamp}-${index}`,
      expectedVersion: index,
      graph: graph(operation),
    });
  }
  const read = () => readWorkflow(page, flow.id);
  const hashes = (await read()).versions.map(
    (item) => `${item.version}:${item.graph_hash}`,
  );
  expect(hashes).toHaveLength(3);

  const second =
    await test.step("saved twice from the editor, it's one draft of the second graph", async () => {
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
      const draft = (await read()).draft;
      expect(draft?.graph.ir_version).toBe(2);
      expect(draft?.graph.nodes?.[1]?.label).toBe("Second draft");
      return draft;
    });
  await test.step("a member who isn't the owner can't save one", async () => {
    // A member who isn't the owner can't save one.
    const member = await signedInPage(users.member);
    const refused = await member.request.put(`${base}/draft`, {
      headers: {
        ...(await writeHeaders(member, `member-${stamp}`)),
        "X-Autobots-Workspace": need("AUTOBOTS_TEST_WORKSPACE_A"),
      },
      data: { graph: graph("lower") },
    });
    await expectRefusal(refused, { status: 403, code: "owner_required" });
    expect((await read()).draft?.graph).toEqual(second?.graph);
  });
  await test.step("a stale publish creates nothing and keeps the draft", async () => {
    // A stale publish creates nothing and keeps the draft.
    const stale = await page.request.post(`${base}/draft/publish`, {
      headers: await writeHeaders(page, `stale-${stamp}`),
      data: { expected_version: 2 },
    });
    await expectRefusal(stale, {
      status: 409,
      code: "workflow_version_conflict",
    });
    const current = await read();
    expect(current.latest_version).toBe(3);
    expect(current.draft).not.toBeNull();
  });
  const fourth =
    await test.step("publishing from the editor creates version 4", async () => {
      // Publishing from the editor names version 3 and creates immutable version 4.
      await page.reload();
      await page.getByRole("button", { name: "Publish saved draft" }).click();
      await expect(page.locator('[data-message="editor"]')).toHaveText(
        "Published the draft as version 4. Earlier versions don't change.",
      );
      const current = await read();
      expect(current.latest_version).toBe(4);
      expect(current.draft).toBeNull();
      expect(current.versions[3]?.graph.nodes?.[1]?.label).toBe("Second draft");
      return current.versions[3]?.graph_hash;
    });
  await test.step("runs and routines can't name a draft, and an execution binds version 4", async () => {
    // Runs and routines can't name a draft. An execution binds a published version's hash.
    await page.request.put(`${base}/draft`, {
      headers: await writeHeaders(page, `again-${stamp}`),
      data: { graph: graph("lower") },
    });
    const draftRun = await page.request.post(`${base}/executions`, {
      headers: await writeHeaders(page, `run-draft-${stamp}`),
      data: { version: "draft", inputs: { in: "x" } },
    });
    await expectRefusal(draftRun, { status: 409, code: "draft_not_runnable" });
    const draftRoutine = await page.request.post("/api/v1/routines", {
      headers: await writeHeaders(page, `routine-draft-${stamp}`),
      data: {
        name: `Draft routine ${stamp}`,
        config: {
          target: { kind: "workflow", id: flow.id, version: "draft" },
          trigger: { kind: "daily", time: "09:00" },
        },
      },
    });
    await expectRefusal(draftRoutine, {
      status: 422,
      code: "draft_not_runnable",
    });
    const binding = await send(page, {
      path: `${base}/executions`,
      key: `run-four-${stamp}`,
      data: { version: 4, inputs: { in: "x" } },
      status: 201,
      parse: parseExecutionBinding,
    });
    expect(binding.workflow_version).toBe(4);
    expect(binding.graph_hash).toBe(fourth);
  });
  await test.step("discarding leaves every published version alone", async () => {
    // Discarding leaves every published version and its hash alone.
    await page.reload();
    await page.getByRole("button", { name: "Discard draft" }).click();
    await expect(page.locator('[data-message="editor"]')).toHaveText(
      "Draft discarded. The published versions are unchanged.",
    );
    const current = await read();
    expect(current.draft).toBeNull();
    expect(
      current.versions
        .slice(0, 3)
        .map((item) => `${item.version}:${item.graph_hash}`),
    ).toEqual(hashes);
    expect(current.versions[3]?.graph_hash).toBe(fourth);
    await expect(page.locator('[data-field="draft-badge"]')).toHaveCount(0);
  });
});

// R-43, WBLD-05: the editor tells its text from the saved draft, and each publish action says which
// one it publishes.
test("unsaved changes are named, and Publish saved draft waits until they're saved", async ({
  page,
}) => {
  await signIn(page, users.owner);
  await page.goto("/workflows");
  const stamp = Date.now();
  const flow = await createWorkflow(page, `unsaved-${stamp}`, {
    name: `Unsaved ${stamp}`,
  });
  await publish(page, flow.id, {
    key: `unsaved-${stamp}`,
    expectedVersion: 0,
    graph: GRAPH,
  });
  await page.goto(`/workflows/${flow.id}`);
  const text = page.getByLabel("Graph");
  const unsaved = page.locator('[data-field="unsaved-badge"]');
  const draftBadge = page.locator('[data-field="draft-badge"]');
  const publishSaved = page.getByRole("button", {
    name: "Publish saved draft",
  });
  const message = page.locator('[data-message="editor"]');

  // The published version opens as it is, with no saved draft to publish.
  await expect(text).not.toHaveValue("");
  expect(JSON.parse(await text.inputValue()).nodes).toHaveLength(3);
  await expect(unsaved).toHaveCount(0);
  await expect(draftBadge).toHaveCount(0);
  await expect(publishSaved).toBeDisabled();
  const published = await text.inputValue();

  // An edit is named until it's saved as the draft.
  await text.fill(
    JSON.stringify({
      ...GRAPH,
      nodes: GRAPH.nodes.map((item) =>
        item.id === "up" ? { ...item, config: { operation: "lower" } } : item,
      ),
    }),
  );
  await expect(unsaved).toHaveText("Unsaved changes");
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(message).toHaveText(
    "Draft saved. Runs keep using the published versions.",
  );
  await expect(unsaved).toHaveCount(0);
  await expect(draftBadge).toBeVisible();
  await expect(publishSaved).toBeEnabled();
  const saved = await text.inputValue();
  expect(JSON.parse(saved).nodes[1].config.operation).toBe("lower");

  // Text that differs from the saved draft can't publish it, and returning to it clears the mark.
  await text.fill(published);
  await expect(unsaved).toBeVisible();
  await expect(draftBadge).toBeVisible();
  await expect(publishSaved).toBeDisabled();
  await text.fill(saved);
  await expect(unsaved).toHaveCount(0);
  await expect(publishSaved).toBeEnabled();

  // Text that isn't JSON is checked once, before either publish action sends anything.
  let sent = 0;
  await page.route(`**/api/v1/workflows/${flow.id}/versions`, (route) => {
    sent += 1;
    return route.continue();
  });
  await text.fill("{ not json");
  await page.getByRole("button", { name: "Publish what is shown" }).click();
  await expect(message).toHaveText("That isn't valid JSON.");
  await expect(publishSaved).toBeDisabled();
  expect(sent).toBe(0);
  await page.unroute(`**/api/v1/workflows/${flow.id}/versions`);
  const current = await readWorkflow(page, flow.id);
  expect(current.latest_version).toBe(1);
  expect(current.draft?.graph.nodes?.[1]?.config).toEqual({
    operation: "lower",
  });
});
