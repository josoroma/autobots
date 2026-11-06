import AxeBuilder from "@axe-core/playwright";
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

async function saveKey(page: Page): Promise<void> {
  await page.goto("/settings/models");
  const source = page.locator('[data-field="source"]');
  await expect(source).toBeVisible();
  if ((await source.textContent())?.trim() === "None") {
    await page
      .getByLabel(/API key|Replace key/)
      .fill("sk-or-valid-arranged-first");
    await page.getByRole("button", { name: "Save & validate" }).click();
    await expect(page.locator('[data-field="auth"]')).toHaveText(
      "The key authenticated.",
    );
  }
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

test("an owner saves revisions in the editor, and a session shows what it really grants", async ({
  page,
}) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
  await saveKey(page);
  await page.goto("/experts");
  await page.getByLabel("Name").fill("Writer");
  await page.getByRole("button", { name: "Create" }).click();
  await expect(page).toHaveURL(/\/experts\/[0-9a-f-]{36}/);
  await expect(
    page.getByRole("heading", { name: "Writer, version 1" }),
  ).toBeVisible();

  await page.getByLabel("Purpose").fill("Writes reports");
  await page.getByLabel("Instructions").fill("Be concise.");
  await page.getByLabel("Calculate").check();
  await page.getByLabel("Model for its work").selectOption("openrouter_terra");
  await page.getByRole("button", { name: "Save revision" }).click();
  await expect(page.locator('[data-message="save"]')).toContainText(
    "Saved as version 2",
  );
  await expect(page.locator('[data-version="1"]')).toContainText("no tools");
  await expect(page.locator('[data-version="2"]')).toContainText("calculate");
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(results.violations.map((violation) => violation.id)).toEqual([]);

  await page.getByRole("button", { name: "Start a session" }).click();
  await expect(page).toHaveURL(/\/sessions\//);
  await expect(page.locator('[data-field="tools"]')).toHaveText(
    "Tools: calculate",
  );
  await expect(page.locator('[data-field="models"]')).toContainText(
    "executor: openrouter_terra",
  );

  await page.getByLabel("Goal").fill("Sum the totals");
  await page.getByRole("button", { name: "Run" }).click();
  await page.getByRole("link", { name: "Open this run" }).click();
  await expect(page.locator('[data-expert="Writer"]')).toContainText(
    "version 2",
  );
  await expect(page.locator('[data-expert="Writer"]')).toContainText(
    "calculate",
  );
  await expect(page.locator('[data-expert="Writer"]')).not.toContainText(
    "save_artifact",
  );
});

test("a stale revision conflicts, and earlier versions never change", async ({
  page,
}) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
  await page.goto("/");
  const created = await page.request.post("/api/v1/experts", {
    headers: await write(page, "e1"),
    data: { name: "Reviser", config: { tools: ["calculate"] } },
  });
  expect(created.status()).toBe(201);
  const expert = await created.json();
  const again = await page.request.post("/api/v1/experts", {
    headers: await write(page, "e1"),
    data: { name: "Reviser", config: { tools: ["calculate"] } },
  });
  expect((await again.json()).id).toBe(expert.id);
  const taken = await page.request.post("/api/v1/experts", {
    headers: await write(page, "e2"),
    data: { name: "Reviser", config: {} },
  });
  expect(taken.status()).toBe(409);
  const saved = await page.request.post(
    `/api/v1/experts/${expert.id}/versions`,
    {
      headers: await write(page, "e3"),
      data: { expected_version: 1, config: { tools: [] } },
    },
  );
  expect((await saved.json()).latest_version).toBe(2);
  const stale = await page.request.post(
    `/api/v1/experts/${expert.id}/versions`,
    {
      headers: await write(page, "e4"),
      data: { expected_version: 1, config: { tools: ["calculate"] } },
    },
  );
  expect(stale.status()).toBe(409);
  expect((await stale.json()).code).toBe("expert_version_conflict");
  const read = await (
    await page.request.get(`/api/v1/experts/${expert.id}`)
  ).json();
  expect(read.versions[0].config.tools).toEqual(["calculate"]);
  expect(read.versions[1].config.tools).toEqual([]);
});

test("a revision can't name a shell, an unknown tool, an unapproved model or an unknown role", async ({
  page,
}) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
  await page.goto("/");
  const cases: [Record<string, unknown>, string | null][] = [
    [{ tools: ["execute"] }, "expert_tool_not_available"],
    [{ tools: ["mcp__server__send"] }, "expert_tool_not_available"],
    [{ tools: ["propose_plan"] }, "expert_tool_not_available"],
    [{ role_bindings: { executor: "openrouter_gpt5" } }, null],
    [
      { role_bindings: { not_a_role: "openrouter_terra" } },
      "expert_role_unknown",
    ],
  ];
  for (const [index, [config, code]] of cases.entries()) {
    const reply = await page.request.post("/api/v1/experts", {
      headers: await write(page, `bad-${index}`),
      data: { name: `Bad ${index}`, config },
    });
    expect(reply.status()).toBe(422);
    if (code !== null) expect((await reply.json()).code).toBe(code);
  }
});

test("a coordinator routes only among its list, and adds nothing", async ({
  page,
}) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
  await saveKey(page);
  await page.goto("/");
  const make = async (name: string, config: Record<string, unknown>) =>
    (
      await (
        await page.request.post("/api/v1/experts", {
          headers: await write(page, `route-${name}`),
          data: { name, config },
        })
      ).json()
    ).id as string;
  const reader = await make("Reader", { tools: ["read_run_file"] });
  const calculator = await make("Calculator", { tools: ["calculate"] });
  const outside = await make("Outside", { tools: ["save_artifact"] });

  await page.goto("/experts");
  await page.getByLabel("Include Reader in a coordinator session").check();
  await page.getByLabel("Include Calculator in a coordinator session").check();
  await page
    .getByRole("button", { name: "Start a coordinator session" })
    .click();
  await expect(page).toHaveURL(/\/sessions\//);
  await expect(page.locator("[data-option]")).toHaveCount(2);
  await expect(
    page.locator('[data-option="Reader"] [data-field="tools"]'),
  ).toHaveText("Tools: read_run_file");
  await expect(
    page.locator('[data-option="Calculator"] [data-field="models"]'),
  ).toContainText("the workspace setting");
  const session = page.url().split("/").at(-1);

  const refused = await page.request.post("/api/v1/runs", {
    headers: await write(page, "route-outside"),
    data: { goal_text: "x", session_id: session, expert_id: outside },
  });
  expect(refused.status()).toBe(409);
  expect((await refused.json()).code).toBe("route_not_granted");
  const unrouted = await page.request.post("/api/v1/runs", {
    headers: await write(page, "route-none"),
    data: { goal_text: "x", session_id: session },
  });
  expect((await unrouted.json()).code).toBe("route_needs_expert");

  await page.getByLabel(/Calculator, version 1/).check();
  await page.getByLabel("Goal").fill("Add it up");
  await page.getByRole("button", { name: "Run" }).click();
  await page.getByRole("link", { name: "Open this run" }).click();
  await expect(page.locator('[data-expert="Calculator"]')).toContainText(
    "calculate",
  );
  await expect(page.locator('[data-expert="Calculator"]')).not.toContainText(
    "read_run_file",
  );
  expect(reader).not.toBe(calculator);
});

test("a member can't save, and another workspace sees nothing", async ({
  browser,
}) => {
  const owner = await (await browser.newContext()).newPage();
  await signIn(owner, EMAIL_A, PASSWORD_A);
  await owner.goto("/");
  const expert = await (
    await owner.request.post("/api/v1/experts", {
      headers: await write(owner, "visibility"),
      data: { name: "Visible", config: {} },
    })
  ).json();
  const other = await (await browser.newContext()).newPage();
  await signIn(other, EMAIL_B, PASSWORD_B);
  expect(
    (await other.request.get(`/api/v1/experts/${expert.id}`)).status(),
  ).toBe(404);
  const foreign = await other.request.post("/api/v1/sessions", {
    headers: await write(other, "foreign"),
    data: { kind: "direct", experts: [{ expert_id: expert.id }] },
  });
  expect(foreign.status()).toBe(404);
  await other.goto(`/experts/${expert.id}`);
  await expect(other.locator('[data-state="unavailable"]')).toBeVisible();
  const member = await (await browser.newContext()).newPage();
  await signIn(member, EMAIL_C, PASSWORD_C);
  const denied = await member.request.post("/api/v1/experts", {
    headers: await write(member, "member"),
    data: { name: "Nope", config: {} },
  });
  expect(denied.status()).toBe(403);
});

test.afterAll(async ({ browser }) => {
  // The settings spec, which runs after this one, expects no key.
  const page = await (await browser.newContext()).newPage();
  await signIn(page, EMAIL_A, PASSWORD_A);
  await page.goto("/settings/models");
  await expect(page.locator('[data-field="auth"]')).toBeVisible();
  await page.getByRole("button", { name: "Disconnect" }).click();
  await expect(page.locator('[data-field="source"]')).toHaveText("None");
});

test("a member can't pin an earlier Expert version through a session, and an owner can", async ({
  browser,
}) => {
  const owner = await (await browser.newContext()).newPage();
  await signIn(owner, EMAIL_A, PASSWORD_A);
  const stamp = Date.now();
  const expert = await (
    await owner.request.post("/api/v1/experts", {
      headers: await write(owner, `pin-expert-${stamp}`),
      data: { name: `Pinned ${stamp}`, config: {} },
    })
  ).json();
  const member = await (await browser.newContext()).newPage();
  await signIn(member, EMAIL_C, PASSWORD_C);
  const workspace = process.env.AUTOBOTS_TEST_WORKSPACE_A ?? "";
  const refused = await member.request.post("/api/v1/sessions", {
    headers: {
      ...(await write(member, `pin-member-${stamp}`)),
      "X-Autobots-Workspace": workspace,
    },
    data: { kind: "direct", experts: [{ expert_id: expert.id, version: 1 }] },
  });
  expect(refused.status()).toBe(403);
  expect((await refused.json()).code).toBe("owner_required");
  const unpinned = await member.request.post("/api/v1/sessions", {
    headers: {
      ...(await write(member, `pin-latest-${stamp}`)),
      "X-Autobots-Workspace": workspace,
    },
    data: { kind: "direct", experts: [{ expert_id: expert.id }] },
  });
  expect(unpinned.status()).toBe(201);
  const pinned = await owner.request.post("/api/v1/sessions", {
    headers: await write(owner, `pin-owner-${stamp}`),
    data: { kind: "direct", experts: [{ expert_id: expert.id, version: 1 }] },
  });
  expect(pinned.status()).toBe(201);
});
