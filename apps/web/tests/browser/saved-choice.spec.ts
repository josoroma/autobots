import { expect, test, type Page } from "@playwright/test";

const EMAIL_A = process.env.AUTOBOTS_TEST_OWNER_EMAIL ?? "";
const PASSWORD_A = process.env.AUTOBOTS_TEST_OWNER_PASSWORD ?? "";
const DEEPSEEK = "openrouter_deepseek_flash";
const TERRA = "openrouter_terra";

// Run by scripts/qualify_identity.py, which arranges each test's saved policy in the database first,
// since a saved choice naming DeepSeek can't be made through the product any more.
async function signIn(page: Page): Promise<void> {
  await page.goto("/sign-in");
  await page.getByLabel("Email").fill(EMAIL_A);
  await page.getByLabel("Password").fill(PASSWORD_A);
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

test("a saved default naming DeepSeek refuses new runs with no substitute, and isn't rewritten", async ({
  page,
}) => {
  await signIn(page);
  await page.goto("/settings/models");
  await expect(page.locator('[data-field="not-offered"]')).toContainText(
    "isn't offered for new runs",
  );
  const choice = page.getByLabel("Workspace default");
  await expect(choice).toHaveValue(DEEPSEEK);
  await expect(choice.locator(`option[value="${DEEPSEEK}"]`)).toBeDisabled();

  const before = await (
    await page.request.get("/api/settings/model-policy")
  ).json();
  const runs = await (await page.request.get("/api/v1/runs")).json();
  const refused = await page.request.post("/api/v1/runs", {
    headers: await write(page, `saved-${Date.now()}`),
    data: { goal_text: "saved default" },
  });
  expect(refused.status()).toBe(409);
  const body = await refused.json();
  expect(body.code).toBe("model_not_offered");
  expect(body.message).toContain("isn't offered for new runs");
  expect((await (await page.request.get("/api/v1/runs")).json()).runs).toEqual(
    runs.runs,
  );

  const intent = await page.request.post("/api/runs/intent", {
    headers: await write(page, `intent-${Date.now()}`),
  });
  expect((await intent.json()).ready).toBe(false);
  expect(
    (
      await (
        await page.request.post("/api/runs/intent", {
          headers: await write(page, `intent-again-${Date.now()}`),
        })
      ).json()
    ).code,
  ).toBe("model_not_offered");

  await page.goto("/");
  // Before anyone presses Run, the page says this would start nothing, and names no route.
  const disclosure = page.locator('[data-disclosure="not-offered"]');
  await expect(disclosure).toContainText("pressing Run would start nothing");
  await expect(page.locator('[data-disclosure="model"]')).toHaveCount(0);
  await page.getByLabel("Model for this run").selectOption(TERRA);
  await expect(disclosure).toHaveCount(0);
  await expect(page.locator('[data-disclosure="model"]')).toContainText(
    "terra",
  );
  await page.getByLabel("Model for this run").selectOption("");
  await expect(disclosure).toBeVisible();
  await page.getByRole("textbox", { name: "Goal" }).fill("kept draft");
  await page.getByRole("button", { name: "Run", exact: true }).click();
  await expect(
    page.getByText(/isn't offered for new runs/).first(),
  ).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Goal" })).toHaveValue(
    "kept draft",
  );

  const after = await (
    await page.request.get("/api/settings/model-policy")
  ).json();
  expect(after.version).toBe(before.version);
  expect(after.default_profile).toBe(DEEPSEEK);

  // A workflow's editor says this only for a version that would call a model.
  const stamp = Date.now();
  const flow = await (
    await page.request.post("/api/v1/workflows", {
      headers: await write(page, `saved-flow-${stamp}`),
      data: { name: `Saved ${stamp}` },
    })
  ).json();
  const input = {
    id: "in",
    block: "input",
    version: 1,
    config: { type: "string" },
  };
  const output = { id: "out", block: "output", version: 1, config: {} };
  const plain = await page.request.post(
    `/api/v1/workflows/${flow.id}/versions`,
    {
      headers: await write(page, `saved-plain-${stamp}`),
      data: {
        expected_version: 0,
        graph: {
          nodes: [input, output],
          links: [
            {
              source: "in",
              source_port: "value",
              target: "out",
              target_port: "value",
            },
          ],
        },
      },
    },
  );
  expect(plain.status()).toBeLessThan(300);
  await page.goto(`/workflows/${flow.id}`);
  await expect(page.locator('[data-disclosure="consent"]')).toBeVisible();
  await expect(page.locator('[data-disclosure="not-offered"]')).toHaveCount(0);
  const expert = await (
    await page.request.post("/api/v1/experts", {
      headers: await write(page, `saved-helper-${stamp}`),
      data: { name: `Saved helper ${stamp}`, config: { tools: ["calculate"] } },
    })
  ).json();
  const withAgent = await page.request.post(
    `/api/v1/workflows/${flow.id}/versions`,
    {
      headers: await write(page, `saved-agent-${stamp}`),
      data: {
        expected_version: 1,
        graph: {
          nodes: [
            input,
            {
              id: "ask",
              block: "agent",
              version: 1,
              config: { expert_id: expert.id },
            },
            output,
          ],
          links: [
            {
              source: "in",
              source_port: "value",
              target: "ask",
              target_port: "goal",
            },
            {
              source: "ask",
              source_port: "result",
              target: "out",
              target_port: "value",
            },
          ],
        },
      },
    },
  );
  expect(withAgent.status()).toBeLessThan(300);
  await page.goto(`/workflows/${flow.id}`);
  await page.getByLabel("Version", { exact: true }).selectOption("2");
  await expect(page.locator('[data-disclosure="not-offered"]')).toContainText(
    "Change it in settings",
  );

  // The way out is the owner's: choosing an offered model, on the screen.
  await page.goto("/settings/models");
  await choice.selectOption(TERRA);
  // Choosing isn't saving, so the warning stays until it is.
  await expect(page.locator('[data-field="not-offered"]')).toBeVisible();
  await page.getByRole("button", { name: "Save policy" }).click();
  await expect(page.locator("[data-policy-message]")).toContainText("Saved.");
  await expect(page.locator('[data-field="not-offered"]')).toHaveCount(0);
});

test("a saved override on another role reads as not taking effect, and still refuses", async ({
  page,
}) => {
  await signIn(page);
  await page.goto("/settings/models");
  const effect = page.locator('[data-field="role-effect"]');
  await expect(effect.locator('[data-role-effect="differs"]')).toHaveText(
    "These differ from the executor, so they don't take effect: coder.",
  );
  await expect(effect.locator('[data-role-effect="summarizer"]')).toHaveCount(
    0,
  );
  await expect(page.locator('[data-field="not-offered"]')).toBeVisible();
  const refused = await page.request.post("/api/v1/runs", {
    headers: await write(page, `override-${Date.now()}`),
    data: { goal_text: "saved override" },
  });
  expect(refused.status()).toBe(409);
  expect((await refused.json()).code).toBe("model_not_offered");
});

test("a saved executor override says every other role differs, summarizer included", async ({
  page,
}) => {
  await signIn(page);
  await page.goto("/settings/models");
  const effect = page.locator('[data-field="role-effect"]');
  await expect(effect.locator('[data-role-effect="differs"]')).toContainText(
    ": coordinator, router, planner, researcher, coder,",
  );
  await expect(effect.locator('[data-role-effect="summarizer"]')).toBeVisible();
});

test("a saved Expert binding says settings won't change it, and the editor says what a save removes", async ({
  page,
}) => {
  await signIn(page);
  await page.goto(`/sessions/${process.env.AUTOBOTS_TEST_STALE_SESSION ?? ""}`);
  const refusal = page.locator('[data-disclosure="not-offered"]');
  await expect(refusal).toContainText("settings won't change it");
  await expect(refusal).not.toContainText("Change it in settings");
  const refused = await page.request.post("/api/v1/runs", {
    headers: await write(page, `stale-${Date.now()}`),
    data: {
      goal_text: "on a stale Expert",
      session_id: process.env.AUTOBOTS_TEST_STALE_SESSION,
      expert_id: process.env.AUTOBOTS_TEST_STALE_EXPERT,
    },
  });
  expect(refused.status()).toBe(409);
  expect((await refused.json()).code).toBe("model_not_offered");
  await page.goto(`/experts/${process.env.AUTOBOTS_TEST_STALE_EXPERT ?? ""}`);
  await expect(page.locator('[data-field="dropped-bindings"]')).toContainText(
    "coder",
  );
  await expect(
    page.getByLabel("Model for its work").locator("option:checked"),
  ).toBeDisabled();
});
