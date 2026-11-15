/**
 * What the visual walk's surfaces need, made once through the app's own routes, each reply's
 * status checked by ../api.ts before it's parsed (US-11.11, TWEB-04), and the signed-in contexts
 * each theme is walked in. The slice suite's scripted worker finishes the run.
 */
import {
  parseExecutionBinding,
  parseExpertView,
  parseSessionView,
  parseWorkflowView,
} from "@autobots/api-client";
import {
  expect,
  type BrowserContext,
  type BrowserContextOptions,
  type Page,
} from "@playwright/test";

import { send } from "../api.ts";
import { signIn, users } from "../auth.ts";
import { inToOut, twoCountsRun } from "../builders.ts";
import { ensureProviderKey } from "../keys.ts";
import { admitRun } from "../runs.ts";
import { WALK_VIEWPORT } from "./probes.ts";
import type { SurfaceContext, SurfaceIds, Theme } from "./surfaces.ts";

/** The fixtures' openContext: a context that closes when the test ends. */
export type OpenContext = (
  options?: BrowserContextOptions,
) => Promise<BrowserContext>;

/** A finished run, so the run and inspector surfaces have what a finished run shows. */
async function finishedRun(page: Page, stamp: number): Promise<string> {
  await ensureProviderKey(page);
  await page.goto("/");
  // A goal with no scenario word, so the scripted worker finishes it plainly.
  const run = await admitRun(page, twoCountsRun("slice-visual"), {
    key: `visual-run-${stamp}`,
  });
  await page.goto(`/runs/${run}`);
  await expect(page.locator("[data-run-status]")).toHaveAttribute(
    "data-run-status",
    "succeeded",
    { timeout: 60_000 },
  );
  return run;
}

/** A published one-step workflow and an execution of it. */
async function executedWorkflow(
  page: Page,
  stamp: number,
): Promise<{ workflow: string; execution: string }> {
  const workflow = await send(page, {
    path: "/api/v1/workflows",
    key: `visual-workflow-${stamp}`,
    data: { name: `Visual ${stamp}` },
    status: 201,
    parse: parseWorkflowView,
  });
  await send(page, {
    path: `/api/v1/workflows/${workflow.id}/versions`,
    key: `visual-version-${stamp}`,
    data: { expected_version: 0, graph: inToOut() },
    status: 201,
    parse: parseWorkflowView,
  });
  const execution = await send(page, {
    path: `/api/v1/workflows/${workflow.id}/executions`,
    key: `visual-execution-${stamp}`,
    data: { version: 1, inputs: { in: "x" } },
    status: 201,
    parse: parseExecutionBinding,
  });
  return { workflow: workflow.id, execution: execution.id };
}

/** Signs workspace A's owner in, makes what the surfaces show, and closes the context. */
export async function arrangeSurfaces(
  openContext: OpenContext,
): Promise<SurfaceIds> {
  const context = await openContext();
  const page = await context.newPage();
  await signIn(page, users.owner);
  const stamp = Date.now();
  const run = await finishedRun(page, stamp);
  const expert = await send(page, {
    path: "/api/v1/experts",
    key: `visual-expert-${stamp}`,
    data: { name: `Visual ${stamp}`, config: { tools: ["calculate"] } },
    status: 201,
    parse: parseExpertView,
  });
  const session = await send(page, {
    path: "/api/v1/sessions",
    key: `visual-session-${stamp}`,
    data: { kind: "direct", experts: [{ expert_id: expert.id }] },
    status: 201,
    parse: parseSessionView,
  });
  const flow = await executedWorkflow(page, stamp);
  await context.close();
  return { run, expert: expert.id, session: session.id, ...flow };
}

/** A context per SurfaceContext, in `theme`, with the owner and the no-key owner signed in. */
export async function openThemedContexts(
  openContext: OpenContext,
  theme: Theme,
): Promise<Record<SurfaceContext, BrowserContext>> {
  const themed = async () => {
    const context = await openContext({ viewport: WALK_VIEWPORT });
    await context.addInitScript((value) => {
      window.localStorage.setItem("autobots.theme", value);
    }, theme);
    return context;
  };
  const contexts = {
    "signed-out": await themed(),
    owner: await themed(),
    "no-key": await themed(),
  };
  for (const [context, user] of [
    [contexts.owner, users.owner],
    [contexts["no-key"], users.noKey],
  ] as const) {
    const page = await context.newPage();
    await signIn(page, user);
    await page.close();
  }
  return contexts;
}
