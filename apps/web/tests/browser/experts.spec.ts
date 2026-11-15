import {
  parseErrorResponse,
  parseExpertView,
  parseRunList,
  parseSessionView,
  parseToolCatalog,
  parseToolGrants,
} from "@autobots/api-client";
import type { Page } from "@playwright/test";

import { expectNoA11yViolations } from "./support/a11y.ts";
import { expectRefusal, getJson, send, writeHeaders } from "./support/api.ts";
import { signIn, users } from "./support/auth.ts";
import { arranged, need } from "./support/env.ts";
import { expect, test } from "./support/fixtures.ts";
import { ensureProviderKey } from "./support/keys.ts";
import { removeProviderKeyIfAny } from "./support/state.ts";

function createExpert(
  page: Page,
  { key, name, config }: { key?: string; name: string; config: object },
) {
  return send(page, {
    path: "/api/v1/experts",
    ...(key === undefined ? {} : { key }),
    data: { name, config },
    status: 201,
    parse: parseExpertView,
  });
}

function readExpert(page: Page, id: string) {
  return getJson(page, {
    path: `/api/v1/experts/${id}`,
    parse: parseExpertView,
  });
}

function runList(page: Page) {
  return getJson(page, { path: "/api/v1/runs", parse: parseRunList });
}

test("an owner saves revisions in the editor, and a session shows what it really grants", async ({
  page,
}) => {
  await signIn(page, users.owner);
  await ensureProviderKey(page);
  await page.goto("/experts");
  await page.getByLabel("Name").fill("Writer");
  await page.getByRole("button", { name: "Create" }).click();
  await expect(page).toHaveURL(/\/experts\/[0-9a-f-]{36}/);
  await expect(
    page.getByRole("heading", { name: "Writer, version 1" }),
  ).toBeVisible();

  // The options come from /api/models, so wait for an offered one before checking DeepSeek is absent.
  const models = page.getByLabel("Model for its work");
  await expect(models.locator('option[value="openrouter_terra"]')).toHaveCount(
    1,
  );
  await expect(
    models.locator('option[value="openrouter_deepseek_flash"]'),
  ).toHaveCount(0);
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
  await expectNoA11yViolations(page);

  await page.getByRole("button", { name: "Start a session" }).click();
  await expect(page).toHaveURL(/\/sessions\//);
  await expect(page.locator('[data-field="tools"]')).toHaveText(
    "Tools: calculate",
  );
  await expect(page.locator('[data-field="models"]')).toContainText(
    "executor: openrouter_terra",
  );

  await page.getByLabel("Goal").fill("Sum the totals");
  await page.getByRole("button", { name: "Run", exact: true }).click();
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
  await signIn(page, users.owner);
  await page.goto("/");
  // The same key replays the first creation.
  const expert = await createExpert(page, {
    key: "e1",
    name: "Reviser",
    config: { tools: ["calculate"] },
  });
  const again = await page.request.post("/api/v1/experts", {
    headers: await writeHeaders(page, "e1"),
    data: { name: "Reviser", config: { tools: ["calculate"] } },
  });
  expect(parseExpertView(await again.json()).id).toBe(expert.id);
  const taken = await page.request.post("/api/v1/experts", {
    headers: await writeHeaders(page, "e2"),
    data: { name: "Reviser", config: {} },
  });
  expect(taken.status()).toBe(409);
  const versions = `/api/v1/experts/${expert.id}/versions`;
  const saved = await send(page, {
    path: versions,
    key: "e3",
    data: { expected_version: 1, config: { tools: [] } },
    status: 201,
    parse: parseExpertView,
  });
  expect(saved.latest_version).toBe(2);
  const stale = await page.request.post(versions, {
    headers: await writeHeaders(page, "e4"),
    data: { expected_version: 1, config: { tools: ["calculate"] } },
  });
  await expectRefusal(stale, { status: 409, code: "expert_version_conflict" });
  const read = await readExpert(page, expert.id);
  expect(read.versions[0]?.config.tools).toEqual(["calculate"]);
  expect(read.versions[1]?.config.tools).toEqual([]);
});

test("a revision can't name a shell, an unknown tool, an unapproved model or an unknown role", async ({
  page,
}) => {
  await signIn(page, users.owner);
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
      headers: await writeHeaders(page, `bad-${index}`),
      data: { name: `Bad ${index}`, config },
    });
    await expectRefusal(reply, {
      status: 422,
      ...(code === null ? {} : { code }),
    });
  }
});

test("a coordinator routes only among its list, and adds nothing", async ({
  page,
}) => {
  await signIn(page, users.owner);
  await ensureProviderKey(page);
  await page.goto("/");
  const make = async (name: string, config: Record<string, unknown>) =>
    (await createExpert(page, { key: `route-${name}`, name, config })).id;
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
    headers: await writeHeaders(page, "route-outside"),
    data: { goal_text: "x", session_id: session, expert_id: outside },
  });
  await expectRefusal(refused, { status: 409, code: "route_not_granted" });
  const unrouted = await page.request.post("/api/v1/runs", {
    headers: await writeHeaders(page, "route-none"),
    data: { goal_text: "x", session_id: session },
  });
  expect(parseErrorResponse(await unrouted.json()).code).toBe(
    "route_needs_expert",
  );

  await page.getByLabel(/Calculator, version 1/).check();
  await page.getByLabel("Goal").fill("Add it up");
  await page.getByRole("button", { name: "Run", exact: true }).click();
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
  asOwner: owner,
  signedInPage,
}) => {
  await owner.goto("/");
  const expert = await createExpert(owner, {
    key: "visibility",
    name: "Visible",
    config: {},
  });
  const other = await signedInPage(users.ownerB);
  expect(
    (await other.request.get(`/api/v1/experts/${expert.id}`)).status(),
  ).toBe(404);
  const foreign = await other.request.post("/api/v1/sessions", {
    headers: await writeHeaders(other, "foreign"),
    data: { kind: "direct", experts: [{ expert_id: expert.id }] },
  });
  expect(foreign.status()).toBe(404);
  await other.goto(`/experts/${expert.id}`);
  await expect(other.locator('[data-state="unavailable"]')).toBeVisible();
  const member = await signedInPage(users.member);
  const denied = await member.request.post("/api/v1/experts", {
    headers: await writeHeaders(member, "member"),
    data: { name: "Nope", config: {} },
  });
  expect(denied.status()).toBe(403);
});

test.afterAll(async ({ browser }) => {
  // Workspace A is left with no key, as settings.spec.ts checks before it starts (TWEB-01).
  await removeProviderKeyIfAny(browser);
});

test("a member can't pin an earlier Expert version through a session, and an owner can", async ({
  asOwner: owner,
  signedInPage,
}) => {
  const stamp = Date.now();
  const expert = await createExpert(owner, {
    key: `pin-expert-${stamp}`,
    name: `Pinned ${stamp}`,
    config: {},
  });
  const member = await signedInPage(users.member);
  const workspace = need("AUTOBOTS_TEST_WORKSPACE_A");
  const refused = await member.request.post("/api/v1/sessions", {
    headers: {
      ...(await writeHeaders(member, `pin-member-${stamp}`)),
      "X-Autobots-Workspace": workspace,
    },
    data: { kind: "direct", experts: [{ expert_id: expert.id, version: 1 }] },
  });
  await expectRefusal(refused, { status: 403, code: "owner_required" });
  const unpinned = await member.request.post("/api/v1/sessions", {
    headers: {
      ...(await writeHeaders(member, `pin-latest-${stamp}`)),
      "X-Autobots-Workspace": workspace,
    },
    data: { kind: "direct", experts: [{ expert_id: expert.id }] },
  });
  expect(unpinned.status()).toBe(201);
  const pinned = await owner.request.post("/api/v1/sessions", {
    headers: await writeHeaders(owner, `pin-owner-${stamp}`),
    data: { kind: "direct", experts: [{ expert_id: expert.id, version: 1 }] },
  });
  expect(pinned.status()).toBe(201);
});

test("saving a revision keeps what the form doesn't edit", async ({ page }) => {
  await signIn(page, users.owner);
  await page.goto("/experts");
  const stamp = Date.now();
  const expert = await createExpert(page, {
    key: `keeps-${stamp}`,
    name: `Keeps ${stamp}`,
    config: {
      skills: ["a-skill"],
      role_bindings: { coder: "openrouter_terra" },
    },
  });
  await page.goto(`/experts/${expert.id}`);
  await page.getByLabel("Purpose").fill("Changed here");
  await page.getByRole("button", { name: "Save revision" }).click();
  await expect(page.getByText(/Saved as version 2/)).toBeVisible();
  const saved = await readExpert(page, expert.id);
  const latest = saved.versions.at(-1)?.config;
  expect(latest?.purpose).toBe("Changed here");
  expect(latest?.skills).toEqual(["a-skill"]);
  expect(latest?.role_bindings).toEqual({ coder: "openrouter_terra" });
});

test("US-14.2: a group grant is previewed, saved as explicit tools, and an unavailable tool is refused", async ({
  page,
}) => {
  await signIn(page, users.owner);
  await page.goto("/experts");
  await page.getByLabel("Name").fill("Grouped");
  await page.getByRole("button", { name: "Create" }).click();
  await expect(
    page.getByRole("heading", { name: "Grouped, version 1" }),
  ).toBeVisible();

  // This stack's API has no GitHub variables, so the connector can't be granted.
  const github = page.locator('[data-tool="create_github_issue"]');
  await expect(github.getByRole("checkbox")).toBeDisabled();
  await expect(github.locator('[data-field="unavailable"]')).toContainText(
    "Unavailable: key not set",
  );
  await expect(
    page.getByLabel(/Connectors group .*includes an unavailable tool/),
  ).toBeDisabled();

  await page.getByLabel("Calculate").check();
  await page.getByLabel(/^Files group \(5 tools\)/).check();
  await expect(page.locator('[data-field="expansion"]')).toHaveText(
    "This version grants: calculate, publish_artifact, read_csv, read_run_file, save_artifact, store_remote_file, from the group files and the tools named.",
  );
  await page.getByRole("button", { name: "Save revision" }).click();
  await expect(page.locator('[data-message="save"]')).toContainText(
    "Saved as version 2",
  );
  const version = page.locator('[data-version="2"]');
  await expect(version).toContainText(
    "calculate, publish_artifact, read_csv, read_run_file, save_artifact, store_remote_file",
  );
  await expect(version).toContainText("(groups: files)");
  await expect(page.locator('[data-version="1"]')).toContainText("no tools");
  await expectNoA11yViolations(page);

  // The stored version names the tools, so it doesn't follow the group later.
  const url = new URL(page.url());
  const id = url.pathname.split("/").at(-1) ?? "";
  const stored = await readExpert(page, id);
  expect(stored.versions[1]?.config.tools).toEqual([
    "calculate",
    "publish_artifact",
    "read_csv",
    "read_run_file",
    "save_artifact",
    "store_remote_file",
  ]);
  expect(stored.versions[1]?.config.tool_groups).toEqual(["files"]);

  for (const [config, code] of [
    [{ tools: ["create_github_issue"] }, "expert_tool_unavailable"],
    [{ tool_groups: ["connectors"] }, "expert_tool_unavailable"],
    [{ tool_groups: ["planning"] }, "expert_tool_group_empty"],
  ] as const) {
    const refused = await page.request.post(`/api/v1/experts/${id}/versions`, {
      headers: await writeHeaders(page),
      data: { expected_version: 2, config },
    });
    await expectRefusal(refused, { status: 422, code });
  }
});

test("US-14.5: a missing key refuses only a run or version that grants its tool", async ({
  page,
}) => {
  // Arranged by tests/db/provider_key_check.py: Experts saved while the GitHub variables were set.
  // This suite's API has none of them.
  const { keyedSession, keyedExpert, plainSession, plainExpert } = arranged({
    keyedSession: "AUTOBOTS_TEST_KEYED_SESSION",
    keyedExpert: "AUTOBOTS_TEST_KEYED_EXPERT",
    plainSession: "AUTOBOTS_TEST_PLAIN_SESSION",
    plainExpert: "AUTOBOTS_TEST_PLAIN_EXPERT",
  });
  await signIn(page, users.owner);
  await ensureProviderKey(page);
  await page.goto("/");
  const before = await runList(page);

  const refused = await page.request.post("/api/v1/runs", {
    headers: await writeHeaders(page),
    data: {
      goal_text: "File the issue",
      session_id: keyedSession,
      expert_id: keyedExpert,
      limit_micro_usd: 1000,
    },
  });
  await expectRefusal(refused, { status: 409, code: "tool_unavailable" });
  const after = await runList(page);
  expect(after.runs.length).toBe(before.runs.length);

  const admitted = await page.request.post("/api/v1/runs", {
    headers: await writeHeaders(page),
    data: {
      goal_text: "Add it up",
      session_id: plainSession,
      expert_id: plainExpert,
      limit_micro_usd: 1000,
    },
  });
  expect(admitted.status()).toBe(202);

  // A version that no longer grants the connector saves, and one that still does is refused.
  const kept = await page.request.post(
    `/api/v1/experts/${keyedExpert}/versions`,
    {
      headers: await writeHeaders(page),
      data: {
        expected_version: 1,
        config: { tools: ["calculate", "create_github_issue"] },
      },
    },
  );
  await expectRefusal(kept, { status: 422, code: "expert_tool_unavailable" });
  const dropped = await page.request.post(
    `/api/v1/experts/${keyedExpert}/versions`,
    {
      headers: await writeHeaders(page),
      data: { expected_version: 1, config: { tools: ["calculate"] } },
    },
  );
  expect(dropped.status()).toBe(201);

  // This suite's API has no provider key but the Jina one arranged in its configuration root's .env
  // (US-14.17), so exactly the keyed tools with no key source read key_missing, and every tool
  // needing no key is unaffected.
  const catalog = await getJson(page, {
    path: "/api/v1/tools",
    parse: parseToolCatalog,
  });
  const tools = catalog.tools;
  const missing = tools
    .filter((tool) => tool.availability === "key_missing")
    .map((tool) => tool.tool_id)
    .sort();
  const keyed = tools
    .filter(
      (tool) =>
        tool.key_requirement !== null && tool.key_requirement.source === null,
    )
    .map((tool) => tool.tool_id)
    .sort();
  expect(missing).toContain("create_github_issue");
  expect(missing).toEqual(keyed);
  expect(
    tools
      .filter((tool) => tool.key_requirement?.source === "environment")
      .map((tool) => tool.tool_id)
      .sort(),
  ).toEqual(["extract_website_content", "search_web"]);
  for (const tool of tools.filter((item) => item.key_requirement === null)) {
    expect(["available", "disabled_by_policy"]).toContain(tool.availability);
  }
  expect(JSON.stringify(catalog)).not.toContain("ghp_");
});

// US-15.6: Experts arranged by SQL (four, with US-15.7's older-version grant) in their own workspace (scripts/qualify_identity.py).
function cardOf(page: Page, name: string) {
  return page
    .locator("li")
    .filter({ has: page.getByRole("link", { name, exact: true }) });
}

test("Expert cards show their facts, filters and the approval note", async ({
  page,
}) => {
  await signIn(page, users.experts);
  await page.goto("/experts");
  const filter = (id: string) => page.locator(`[data-filter="${id}"]`);
  await expect(filter("all")).toHaveText("All 4");
  await expect(filter("outside")).toHaveText("Can change things outside 1");
  await expect(filter("read_only")).toHaveText("Read only 3");

  const watcher = cardOf(page, "Market watcher");
  await expect(watcher.locator('[data-field="role"]')).toHaveText(
    "executor · Terra · version 1",
  );
  await expect(watcher).toContainText("market_history");
  await expect(watcher).toContainText("+2");
  await expect(watcher.locator('[data-field="runs"]')).toHaveText(
    /^3 runs · last run (just now|\d+ minutes? ago)$/,
  );
  await expect(
    watcher.getByRole("button", { name: "Start run with Market watcher" }),
  ).toBeVisible();
  await expect(
    cardOf(page, "Issue triager").locator('[data-field="approval"]'),
  ).toHaveText("Approval on every issue");
  await expect(
    cardOf(page, "Brief writer").locator('[data-field="approval"]'),
  ).toHaveCount(0);
  await expectNoA11yViolations(page);

  const names = async () =>
    (await page.locator("main li a[href^='/experts/']").allTextContents()).map(
      (text) => text.trim(),
    );
  await filter("outside").click();
  expect(await names()).toEqual(["Issue triager"]);
  await filter("read_only").click();
  expect((await names()).sort()).toEqual([
    "Brief writer",
    "Market watcher",
    "Old granter",
  ]);
  await filter("all").click();
  await page.getByPlaceholder("Search Experts").fill("brief");
  expect(await names()).toEqual(["Brief writer"]);
});

test("Start run opens run creation with the disclosure, and sends nothing", async ({
  page,
}) => {
  await signIn(page, users.experts);
  const before = (await runList(page)).total;
  await page.goto("/experts");
  await cardOf(page, "Brief writer")
    .getByRole("button", { name: "Start run with Brief writer" })
    .click();
  await expect(page).toHaveURL(/\/sessions\//);
  await expect(page.locator('[data-field="disclosure"]')).toContainText(
    "Nothing is sent until you press Run",
  );
  const after = (await runList(page)).total;
  expect(after).toBe(before);
});

// US-15.7: who a tool is granted to, from the latest Expert versions and published workflows.
test("a tool's detail lists who it's granted to now", async ({ page }) => {
  await signIn(page, users.experts);
  await page.goto("/tools?tool=read_csv");
  const panel = page.locator('[data-panel="read_csv"]');
  const granted = panel.locator('[data-field="granted-to"]');
  await expect(
    granted.getByRole("link", { name: "Expert Market watcher, version 1" }),
  ).toBeVisible();
  await expect(
    granted.getByRole("link", { name: "Expert Issue triager, version 1" }),
  ).toBeVisible();
  await expect(
    granted.getByRole("link", { name: "Workflow Nightly triage, version 1" }),
  ).toBeVisible();
  await expect(granted).not.toContainText("Old granter");
  const grants = await getJson(page, {
    path: "/api/v1/tools/read_csv/grants",
    parse: parseToolGrants,
  });
  expect(grants.experts.map((item) => item.name).sort()).toEqual([
    "Issue triager",
    "Market watcher",
  ]);
  expect(grants.workflows.map((item) => item.name)).toEqual(["Nightly triage"]);
  await expectNoA11yViolations(page);
});

// R-18 step 1, Decision 0027 D2: the route answers the admission for the API, so this starts no
// run and spends nothing.
test("a double click on Run in a session sends one admission", async ({
  page,
}) => {
  await signIn(page, users.owner);
  await page.goto("/");
  const expert = (
    await createExpert(page, {
      key: `double-${Date.now()}`,
      name: `Pressed twice ${Date.now()}`,
      config: {},
    })
  ).id;
  const session = (
    await send(page, {
      path: "/api/v1/sessions",
      key: `double-session-${Date.now()}`,
      data: { kind: "direct", experts: [{ expert_id: expert }] },
      status: 201,
      parse: parseSessionView,
    })
  ).id;

  let posts = 0;
  await page.route("**/api/v1/runs", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    posts += 1;
    await new Promise((settle) => setTimeout(settle, 400));
    await route.fulfill({
      status: 202,
      json: {
        schema_version: 1,
        run_id: "22222222-2222-4222-8222-222222222222",
        status: "queued",
        version: 1,
        replayed: false,
      },
    });
  });
  await page.goto(`/sessions/${session}`);
  await page.getByLabel("Goal").fill("Pressed twice, admitted once");
  await page.getByRole("button", { name: "Run", exact: true }).dblclick();
  await expect(page.getByRole("link", { name: "Open this run" })).toBeVisible();
  expect(posts).toBe(1);
  await page.unroute("**/api/v1/runs");
});
