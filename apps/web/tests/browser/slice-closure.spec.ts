import {
  parseApprovalList,
  parseApprovalResult,
  parseExpertView,
  parseProviderStatus,
  parseRunInspector,
  parseRunList,
  parseSessionView,
} from "@autobots/api-client";
import type { Page } from "@playwright/test";

import { expectRefusal, getJson, send, writeHeaders } from "./support/api.ts";
import { signIn, users } from "./support/auth.ts";
import { compactingGoal, delegatingGoal } from "./support/builders.ts";
import { arranged } from "./support/env.ts";
import { expect, test } from "./support/fixtures.ts";
import { ensureProviderKey } from "./support/keys.ts";
import { admitRun } from "./support/runs.ts";

const runs = arranged({
  keyless: "AUTOBOTS_TEST_FILES_RUN",
  waiting: "AUTOBOTS_TEST_WAITING_RUN",
});
const CLOSURE_KEY = "sk-or-valid-arranged-closure";

function inspector(page: Page, run: string) {
  return getJson(page, {
    path: `/api/v1/runs/${run}/inspector`,
    parse: parseRunInspector,
  });
}

const finished = (page: Page, status: string) =>
  expect(page.locator("[data-run-status]")).toHaveAttribute(
    "data-run-status",
    status,
    { timeout: 60_000 },
  );

test("the goal and its criteria read the same after a compaction as before it", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await signIn(page, users.owner);
  await ensureProviderKey(page, CLOSURE_KEY);
  await page.goto("/");
  const stamp = Date.now();
  const goal = `${compactingGoal(stamp)}: keep this goal whole`;
  const criterion = "The report states the total";
  const id = await admitRun(
    page,
    { goal_text: goal, acceptance_criteria: [criterion] },
    { key: `compact-${stamp}` },
  );
  await page.goto(`/runs/${id}`);
  const main = page.locator("main");
  await expect(main).toContainText(goal);
  await expect(main).toContainText(criterion);
  const summarized = async () =>
    (await inspector(page, id)).model_calls.filter(
      (call) => call.role === "summarizer" && call.status === "succeeded",
    ).length;
  // This first read really is before it: the worker takes its time over the early steps.
  expect(await summarized()).toBe(0);
  await finished(page, "succeeded");
  await page.reload();
  await expect(main).toContainText(goal);
  await expect(main).toContainText(criterion);
  // Compaction really happened: it's on the ledger under its own role.
  expect(await summarized()).toBeGreaterThan(0);
});

test("the Assignments card shows a child's Expert and outcome, and each run links to the other", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await signIn(page, users.owner);
  await ensureProviderKey(page, CLOSURE_KEY);
  await page.goto("/");
  const stamp = Date.now();
  const tools = ["calculate", "save_artifact", "publish_artifact"];
  const expert = async (name: string): Promise<string> =>
    (
      await send(page, {
        path: "/api/v1/experts",
        key: `${name}-${stamp}`,
        data: { name: `${name} ${stamp}`, config: { tools } },
        status: 201,
        parse: parseExpertView,
      })
    ).id;
  const lead = await expert("Closure lead");
  const helper = await expert("Closure helper");
  const session = await send(page, {
    path: "/api/v1/sessions",
    key: `closure-session-${stamp}`,
    data: {
      kind: "coordinator",
      experts: [{ expert_id: lead }, { expert_id: helper }],
    },
    status: 201,
    parse: parseSessionView,
  });
  const id = await admitRun(
    page,
    {
      goal_text: delegatingGoal(helper),
      session_id: session.id,
      expert_id: lead,
    },
    { key: `closure-run-${stamp}` },
  );
  await page.goto(`/runs/${id}`);
  const card = page.getByRole("region", { name: "Assignments" });
  const item = card.locator('[data-assignment="finished"]');
  await expect(item).toBeVisible({ timeout: 60_000 });
  await expect(item).toContainText(`Closure helper ${stamp}`);
  await expect(item).toContainText("succeeded");
  await item.getByRole("link").click();
  await expect(page).not.toHaveURL(new RegExp(id));
  await finished(page, "succeeded");
  const parent = page.locator('[data-field="parent-run"]');
  await expect(parent.getByRole("link")).toHaveAttribute("href", `/runs/${id}`);
});

test("a run's plan, approval, artifact and status come back after the connection drops", async ({
  page,
}) => {
  await signIn(page, users.owner);
  await page.goto(`/runs/${runs.waiting}`);
  await expect(page.locator("[data-run-status]")).toHaveAttribute(
    "data-run-status",
    "waiting_approval",
  );
  const main = page.locator("main");
  await expect(main.locator("[data-task-status]")).toHaveCount(1);
  await expect(main).toContainText("Write the report");
  await expect(main.locator("[data-artifact-status]")).toHaveCount(1);
  await expect(main).toContainText("Approval requested for send_blind");
  await expect(page.locator("[data-connection]")).toHaveAttribute(
    "data-connection",
    "live",
  );
  const before = await main.locator("[data-sequence]").count();
  // A real loss of the network for this page. The decision goes through Node, so it commits meanwhile.
  await page.context().setOffline(true);
  await expect(page.locator("[data-connection]")).toHaveAttribute(
    "data-connection",
    "reconnecting",
    { timeout: 15_000 },
  );
  const pending = await getJson(page, {
    path: "/api/v1/approvals",
    parse: parseApprovalList,
  });
  const request = pending.approvals.find(
    (item) => item.run_id === runs.waiting,
  );
  if (request === undefined)
    throw new Error("The run's request isn't waiting.");
  await send(page, {
    path: `/api/v1/approvals/${request.id}/decision`,
    key: `closure-decide-${Date.now()}`,
    data: { decision: "reject", argument_hash: request.argument_hash },
    status: 200,
    parse: parseApprovalResult,
  });
  await page.context().setOffline(false);
  // This event was committed during the drop, so only a rebuild can show it.
  await expect(main).toContainText("Approval reject", { timeout: 20_000 });
  await expect(page.locator("[data-run-status]")).not.toHaveAttribute(
    "data-run-status",
    "waiting_approval",
    { timeout: 20_000 },
  );
  await expect(main).toContainText("Write the report");
  await expect(main.locator("[data-artifact-status]")).toContainText("report");
  // And all of it from the server's state, with nothing held over from before the drop.
  await page.reload();
  await expect(main).toContainText("Approval requested for send_blind");
  await expect(main).toContainText("Approval reject");
  await expect(main).toContainText("Write the report");
  await expect(main.locator("[data-artifact-status]")).toContainText("report");
  // Every event in order, with no gap. Events are keyed by sequence, so a duplicate can't render.
  await expect
    .poll(() => main.locator("[data-sequence]").count(), { timeout: 20_000 })
    .toBeGreaterThan(before);
  const sequences = await main
    .locator("[data-sequence]")
    .evaluateAll((items) =>
      items.map((item) => Number(item.getAttribute("data-sequence"))),
    );
  const ordered = [...sequences].sort((a, b) => a - b);
  expect(ordered).toEqual(
    ordered.map((_, index) => (ordered[0] as number) + index),
  );
});

test("with no key, a run's artifacts can be listed and downloaded, and inference is refused", async ({
  page,
}) => {
  await signIn(page, users.files);
  const status = await getJson(page, {
    path: "/api/settings/model-providers",
    parse: parseProviderStatus,
  });
  expect(status.source).toBe("none");
  await page.goto(`/runs/${runs.keyless}`);
  const artifact = page.locator('[data-artifact-status="published"]');
  await expect(artifact).toContainText("report");
  const href = await artifact.getByRole("link").first().getAttribute("href");
  const download = await page.request.get(href ?? "");
  expect(download.status()).toBe(200);
  expect(await download.text()).toContain("Total: 5");
  const callsBefore = (await inspector(page, runs.keyless)).model_calls.length;
  const refused = await page.request.post("/api/v1/runs", {
    headers: await writeHeaders(page, `keyless-${Date.now()}`),
    data: { goal_text: "needs a model" },
  });
  await expectRefusal(refused, { status: 409, code: "credentials_required" });
  // Nothing started: the same one run, and no call added to its ledger.
  const listed = await getJson(page, {
    path: "/api/v1/runs",
    parse: parseRunList,
  });
  expect(listed.runs.map((run) => run.id)).toEqual([runs.keyless]);
  expect((await inspector(page, runs.keyless)).model_calls.length).toBe(
    callsBefore,
  );
});
