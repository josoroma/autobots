/**
 * Renaming a workflow through the BFF and the editor (Decision 0037 N1 to N5, US-19.1): the owner
 * renames it, the editor sends the name trimmed and never a blank one, a taken name and a name
 * outside creation's rule are refused, a member is refused, and nothing but the name changes.
 */
import { parseWorkflowView } from "@autobots/api-client";
import type { Page } from "@playwright/test";

import { csrfHeaders, expectRefusal, getJson, send } from "./support/api.ts";
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

function readWorkflow(
  page: Page,
  id: string,
  headers?: Record<string, string>,
) {
  return getJson(page, {
    path: `/api/v1/workflows/${id}`,
    parse: parseWorkflowView,
    ...(headers === undefined ? {} : { headers }),
  });
}

test("the owner renames a workflow in the editor, a member can't, and nothing else changes", async ({
  page,
  signedInPage,
}) => {
  await signIn(page, users.owner);
  await page.goto("/workflows");
  const stamp = Date.now();
  const flow = await createWorkflow(page, `renamed-${stamp}`, {
    name: `Before ${stamp}`,
    description: "Shouts the topic back",
  });
  await send(page, {
    path: `/api/v1/workflows/${flow.id}/versions`,
    key: `renamed-${stamp}-p`,
    data: { expected_version: 0, graph: GRAPH },
    status: 201,
    parse: parseWorkflowView,
  });
  const taken = await createWorkflow(page, `taken-${stamp}`, {
    name: `Taken ${stamp}`,
  });
  const before = await readWorkflow(page, flow.id);
  const after = `After ${stamp}`;
  const message = page.locator('[data-message="editor"]');
  const heading = page.locator("#graph-heading");
  const nameField = page.getByLabel("Name", { exact: true });
  const isRename = (url: string, method: string) =>
    url.endsWith(`/api/v1/workflows/${flow.id}/name`) && method === "PUT";

  await test.step("the editor sends the name trimmed, with no key, and only the name changes", async () => {
    await page.goto(`/workflows/${flow.id}`);
    const renamed = page.waitForRequest((request) =>
      isRename(request.url(), request.method()),
    );
    await nameField.fill(`  ${after}  `);
    await page.getByRole("button", { name: "Save name" }).click();
    const sent = await renamed;
    expect(sent.postDataJSON()).toEqual({ name: after });
    expect(sent.headers()["idempotency-key"]).toBeUndefined();
    await expect(message).toHaveText("Name saved. No version changed.");
    await expect(heading).toHaveText(after);
    await expect(page.getByText("Version 1", { exact: true })).toBeVisible();
    const read = await readWorkflow(page, flow.id);
    expect(read.name).toBe(after);
    expect({ ...read, name: before.name }).toEqual(before);
  });

  await test.step("the list and the preview show the new name", async () => {
    await page.goto(`/workflows?workflow=${flow.id}`);
    await expect(
      page.getByRole("link", { name: after, exact: true }),
    ).toBeVisible();
    await expect(page.getByText(`Preview: ${after}`)).toBeVisible();
  });

  await test.step("a cleared name sends nothing, and a taken one is refused and changes nothing", async () => {
    await page.goto(`/workflows/${flow.id}`);
    let sent = 0;
    page.on("request", (request) => {
      if (isRename(request.url(), request.method())) sent += 1;
    });
    await nameField.fill("   ");
    await page.getByRole("button", { name: "Save name" }).click();
    await expect(message).toHaveText("A workflow needs a name.");
    expect(sent).toBe(0);
    await nameField.fill(`Taken ${stamp}`);
    const refused = page.waitForResponse((reply) =>
      isRename(reply.url(), reply.request().method()),
    );
    await page.getByRole("button", { name: "Save name" }).click();
    expect((await refused).status()).toBe(409);
    await expect(message).toHaveText("That name is already used.");
    await expect(heading).toHaveText(after);
    expect((await readWorkflow(page, flow.id)).name).toBe(after);
    expect((await readWorkflow(page, taken.id)).name).toBe(`Taken ${stamp}`);
  });

  await test.step("the API refuses an empty and a 101-character name", async () => {
    for (const name of ["", "x".repeat(101)]) {
      const reply = await page.request.put(
        `/api/v1/workflows/${flow.id}/name`,
        { headers: await csrfHeaders(page), data: { name } },
      );
      await expectRefusal(reply, { status: 422, code: "invalid_request" });
    }
    expect((await readWorkflow(page, flow.id)).name).toBe(after);
  });

  await test.step("a member reads the name and is refused a rename", async () => {
    // The member belongs to more than one workspace, so each request names the owner's.
    const member = await signedInPage(users.member);
    const workspace = {
      "X-Autobots-Workspace": need("AUTOBOTS_TEST_WORKSPACE_A"),
    };
    expect((await readWorkflow(member, flow.id, workspace)).name).toBe(after);
    const denied = await member.request.put(
      `/api/v1/workflows/${flow.id}/name`,
      {
        headers: { ...(await csrfHeaders(member)), ...workspace },
        data: { name: `Member ${stamp}` },
      },
    );
    await expectRefusal(denied, { status: 403, code: "owner_required" });
    expect((await readWorkflow(page, flow.id)).name).toBe(after);
  });
});
