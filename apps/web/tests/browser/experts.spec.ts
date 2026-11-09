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

  await expect(
    page
      .getByLabel("Model for its work")
      .locator('option[value="openrouter_deepseek_flash"]'),
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

test("saving a revision keeps what the form doesn't edit", async ({ page }) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
  await page.goto("/experts");
  const token = await (await page.request.get("/api/csrf")).json();
  const stamp = Date.now();
  const headers = (key: string) => ({
    [token.header]: token.token,
    Origin: new URL(page.url()).origin,
    "Content-Type": "application/json",
    "Idempotency-Key": `${key}-${stamp}`,
  });
  const expert = await (
    await page.request.post("/api/v1/experts", {
      headers: headers("keeps"),
      data: {
        name: `Keeps ${stamp}`,
        config: {
          skills: ["a-skill"],
          role_bindings: { coder: "openrouter_terra" },
        },
      },
    })
  ).json();
  await page.goto(`/experts/${expert.id}`);
  await page.getByLabel("Purpose").fill("Changed here");
  await page.getByRole("button", { name: "Save revision" }).click();
  await expect(page.getByText(/Saved as version 2/)).toBeVisible();
  const saved = await (
    await page.request.get(`/api/v1/experts/${expert.id}`)
  ).json();
  const latest = saved.versions.at(-1).config;
  expect(latest.purpose).toBe("Changed here");
  expect(latest.skills).toEqual(["a-skill"]);
  expect(latest.role_bindings).toEqual({ coder: "openrouter_terra" });
});

test("US-14.2: a group grant is previewed, saved as explicit tools, and an unavailable tool is refused", async ({
  page,
}) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
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
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(results.violations.map((violation) => violation.id)).toEqual([]);

  // The stored version names the tools, so it doesn't follow the group later.
  const url = new URL(page.url());
  const id = url.pathname.split("/").at(-1) ?? "";
  const stored = await (await page.request.get(`/api/v1/experts/${id}`)).json();
  expect(stored.versions[1].config.tools).toEqual([
    "calculate",
    "publish_artifact",
    "read_csv",
    "read_run_file",
    "save_artifact",
    "store_remote_file",
  ]);
  expect(stored.versions[1].config.tool_groups).toEqual(["files"]);

  for (const [config, code] of [
    [{ tools: ["create_github_issue"] }, "expert_tool_unavailable"],
    [{ tool_groups: ["connectors"] }, "expert_tool_unavailable"],
    [{ tool_groups: ["planning"] }, "expert_tool_group_empty"],
  ] as const) {
    const refused = await page.request.post(`/api/v1/experts/${id}/versions`, {
      headers: await write(page, crypto.randomUUID()),
      data: { expected_version: 2, config },
    });
    expect(refused.status()).toBe(422);
    expect((await refused.json()).code).toBe(code);
  }
});

test("US-14.5: a missing key refuses only a run or version that grants its tool", async ({
  page,
}) => {
  // Arranged by tests/db/provider_key_check.py: Experts saved while the GitHub variables were set.
  // This suite's API has none of them.
  const keyedSession = process.env.AUTOBOTS_TEST_KEYED_SESSION ?? "";
  const keyedExpert = process.env.AUTOBOTS_TEST_KEYED_EXPERT ?? "";
  const plainSession = process.env.AUTOBOTS_TEST_PLAIN_SESSION ?? "";
  const plainExpert = process.env.AUTOBOTS_TEST_PLAIN_EXPERT ?? "";
  expect(keyedSession).not.toBe("");
  await signIn(page, EMAIL_A, PASSWORD_A);
  await saveKey(page);
  await page.goto("/");
  const before = await (await page.request.get("/api/v1/runs")).json();

  const refused = await page.request.post("/api/v1/runs", {
    headers: await write(page, crypto.randomUUID()),
    data: {
      goal_text: "File the issue",
      session_id: keyedSession,
      expert_id: keyedExpert,
      limit_micro_usd: 1000,
    },
  });
  expect(refused.status()).toBe(409);
  expect((await refused.json()).code).toBe("tool_unavailable");
  const after = await (await page.request.get("/api/v1/runs")).json();
  expect(after.runs.length).toBe(before.runs.length);

  const admitted = await page.request.post("/api/v1/runs", {
    headers: await write(page, crypto.randomUUID()),
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
      headers: await write(page, crypto.randomUUID()),
      data: {
        expected_version: 1,
        config: { tools: ["calculate", "create_github_issue"] },
      },
    },
  );
  expect(kept.status()).toBe(422);
  expect((await kept.json()).code).toBe("expert_tool_unavailable");
  const dropped = await page.request.post(
    `/api/v1/experts/${keyedExpert}/versions`,
    {
      headers: await write(page, crypto.randomUUID()),
      data: { expected_version: 1, config: { tools: ["calculate"] } },
    },
  );
  expect(dropped.status()).toBe(201);

  // This suite's API has no provider key but the Jina one arranged in its configuration root's .env
  // (US-14.17), so exactly the keyed tools with no key source read key_missing, and every tool
  // needing no key is unaffected.
  const catalog = await (await page.request.get("/api/v1/tools")).json();
  type Tool = {
    tool_id: string;
    availability: string;
    key_requirement: { credential: string; source: string | null } | null;
  };
  const tools = catalog.tools as Tool[];
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
const EXPERTS_EMAIL = process.env.AUTOBOTS_TEST_EXPERTS_EMAIL ?? "";
const EXPERTS_PASSWORD = process.env.AUTOBOTS_TEST_EXPERTS_PASSWORD ?? "";

function cardOf(page: Page, name: string) {
  return page
    .locator("li")
    .filter({ has: page.getByRole("link", { name, exact: true }) });
}

test("Expert cards show their facts, filters and the approval note", async ({
  page,
}) => {
  await signIn(page, EXPERTS_EMAIL, EXPERTS_PASSWORD);
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
    /^3 runs · last \d+ min ago$/,
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
  const axe = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(axe.violations.map((item) => item.id)).toEqual([]);

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
  await signIn(page, EXPERTS_EMAIL, EXPERTS_PASSWORD);
  const before = (await (await page.request.get("/api/v1/runs")).json()).total;
  await page.goto("/experts");
  await cardOf(page, "Brief writer")
    .getByRole("button", { name: "Start run with Brief writer" })
    .click();
  await expect(page).toHaveURL(/\/sessions\//);
  await expect(page.locator('[data-field="disclosure"]')).toContainText(
    "Nothing is sent until you press Run",
  );
  const after = (await (await page.request.get("/api/v1/runs")).json()).total;
  expect(after).toBe(before);
});

// US-15.7: who a tool is granted to, from the latest Expert versions and published workflows.
test("a tool's detail lists who it's granted to now", async ({ page }) => {
  await signIn(page, EXPERTS_EMAIL, EXPERTS_PASSWORD);
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
  const grants = await (
    await page.request.get("/api/v1/tools/read_csv/grants")
  ).json();
  expect(
    grants.experts.map((item: { name: string }) => item.name).sort(),
  ).toEqual(["Issue triager", "Market watcher"]);
  expect(grants.workflows.map((item: { name: string }) => item.name)).toEqual([
    "Nightly triage",
  ]);
  const axe = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(axe.violations.map((item) => item.id)).toEqual([]);
});
