import {
  parseExpertView,
  parseModelPolicyState,
  parseRunIntentCheck,
  parseRunList,
  parseWorkflowView,
} from "@autobots/api-client";
import type { Page } from "@playwright/test";

import { expectRefusal, getJson, send, writeHeaders } from "./support/api.ts";
import { signIn, users } from "./support/auth.ts";
import { link, node } from "./support/builders.ts";
import { need } from "./support/env.ts";
import { expect, test } from "./support/fixtures.ts";

const DEEPSEEK = "openrouter_deepseek_flash";
const TERRA = "openrouter_terra";

// Run by scripts/qualify_identity.py, which arranges each test's saved policy in the database first,
// since a saved choice naming DeepSeek can't be made through the product any more.

function policy(page: Page) {
  return getJson(page, {
    path: "/api/settings/model-policy",
    parse: parseModelPolicyState,
  });
}

function runList(page: Page) {
  return getJson(page, { path: "/api/v1/runs", parse: parseRunList });
}

async function refusedRun(page: Page, key: string, data: object) {
  const reply = await page.request.post("/api/v1/runs", {
    headers: await writeHeaders(page, key),
    data,
  });
  return expectRefusal(reply, { status: 409, code: "model_not_offered" });
}

test("a saved default naming DeepSeek refuses new runs with no substitute, and isn't rewritten", async ({
  page,
}) => {
  await signIn(page, users.owner);
  await page.goto("/settings/models");
  await expect(page.locator('[data-field="not-offered"]')).toContainText(
    "isn't offered for new runs",
  );
  const choice = page.getByLabel("Workspace default");
  await expect(choice).toHaveValue(DEEPSEEK);
  await expect(choice.locator(`option[value="${DEEPSEEK}"]`)).toBeDisabled();

  const before = await policy(page);
  const runs = await runList(page);
  const body = await refusedRun(page, `saved-${Date.now()}`, {
    goal_text: "saved default",
  });
  expect(body.message).toContain("isn't offered for new runs");
  expect((await runList(page)).runs).toEqual(runs.runs);

  const intent = (key: string) =>
    send(page, {
      path: "/api/v1/runs/intent",
      key,
      status: 200,
      parse: parseRunIntentCheck,
    });
  expect((await intent(`intent-${Date.now()}`)).ready).toBe(false);
  expect((await intent(`intent-again-${Date.now()}`)).code).toBe(
    "model_not_offered",
  );

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

  const after = await policy(page);
  expect(after.version).toBe(before.version);
  expect(after.default_profile).toBe(DEEPSEEK);

  // A workflow's editor says this only for a version that would call a model.
  const stamp = Date.now();
  const flow = await send(page, {
    path: "/api/v1/workflows",
    key: `saved-flow-${stamp}`,
    data: { name: `Saved ${stamp}` },
    status: 201,
    parse: parseWorkflowView,
  });
  const input = node("in", "input", { type: "string" });
  const output = node("out", "output");
  const versions = `/api/v1/workflows/${flow.id}/versions`;
  const plain = await page.request.post(versions, {
    headers: await writeHeaders(page, `saved-plain-${stamp}`),
    data: {
      expected_version: 0,
      graph: {
        nodes: [input, output],
        links: [link("in", "value", "out", "value")],
      },
    },
  });
  expect(plain.status()).toBeLessThan(300);
  await page.goto(`/workflows/${flow.id}`);
  await expect(page.locator('[data-disclosure="consent"]')).toBeVisible();
  await expect(page.locator('[data-disclosure="not-offered"]')).toHaveCount(0);
  const expert = await send(page, {
    path: "/api/v1/experts",
    key: `saved-helper-${stamp}`,
    data: { name: `Saved helper ${stamp}`, config: { tools: ["calculate"] } },
    status: 201,
    parse: parseExpertView,
  });
  const withAgent = await page.request.post(versions, {
    headers: await writeHeaders(page, `saved-agent-${stamp}`),
    data: {
      expected_version: 1,
      graph: {
        nodes: [input, node("ask", "agent", { expert_id: expert.id }), output],
        links: [
          link("in", "value", "ask", "goal"),
          link("ask", "result", "out", "value"),
        ],
      },
    },
  });
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
  await signIn(page, users.owner);
  await page.goto("/settings/models");
  const effect = page.locator('[data-field="role-effect"]');
  await expect(effect.locator('[data-role-effect="differs"]')).toHaveText(
    "These differ from the executor, so they don't take effect: coder.",
  );
  await expect(effect.locator('[data-role-effect="summarizer"]')).toHaveCount(
    0,
  );
  await expect(page.locator('[data-field="not-offered"]')).toBeVisible();
  await refusedRun(page, `override-${Date.now()}`, {
    goal_text: "saved override",
  });
});

test("a saved executor override says every other role differs, summarizer included", async ({
  page,
}) => {
  await signIn(page, users.owner);
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
  const session = need("AUTOBOTS_TEST_STALE_SESSION");
  const staleExpert = need("AUTOBOTS_TEST_STALE_EXPERT");
  await signIn(page, users.owner);
  await page.goto(`/sessions/${session}`);
  const refusal = page.locator('[data-disclosure="not-offered"]');
  await expect(refusal).toContainText("settings won't change it");
  await expect(refusal).not.toContainText("Change it in settings");
  await refusedRun(page, `stale-${Date.now()}`, {
    goal_text: "on a stale Expert",
    session_id: session,
    expert_id: staleExpert,
  });
  await page.goto(`/experts/${staleExpert}`);
  await expect(page.locator('[data-field="dropped-bindings"]')).toContainText(
    "coder",
  );
  await expect(
    page.getByLabel("Model for its work").locator("option:checked"),
  ).toBeDisabled();
});
