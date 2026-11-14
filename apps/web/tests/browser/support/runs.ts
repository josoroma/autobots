/**
 * Runs admitted, read and commanded through the BFF, each reply checked against the generated
 * contract (TWEB-04, TWEB-19). Admission needs a usable key, which keys.ts arranges separately.
 */
import {
  parseRunAccepted,
  parseRunSummary,
  type RunRequest,
  type RunSummary,
} from "@autobots/api-client";
import type { APIResponse, Page } from "@playwright/test";

import { isTerminal } from "../../../lib/runs/status.ts";
import { getJson, send, writeHeaders } from "./api.ts";

/** Admits a run and returns its ID, asserting the 202. `key` defaults to a fresh one. */
export async function admitRun(
  page: Page,
  data: RunRequest,
  { key }: { key?: string } = {},
): Promise<string> {
  const accepted = await send(page, {
    path: "/api/v1/runs",
    data,
    ...(key === undefined ? {} : { key }),
    status: 202,
    parse: parseRunAccepted,
  });
  return accepted.run_id;
}

/** The run's summary, as the API reports it now. */
export function readRun(page: Page, run: string): Promise<RunSummary> {
  return getJson(page, { path: `/api/v1/runs/${run}`, parse: parseRunSummary });
}

/** Sends a pause, resume or cancel under `expectedVersion`, and returns the reply as it came. */
export async function runCommand(
  page: Page,
  {
    run,
    command,
    expectedVersion,
    key,
  }: {
    run: string;
    command: "pause" | "resume" | "cancel";
    expectedVersion: number;
    key?: string;
  },
): Promise<APIResponse> {
  return page.request.post(`/api/v1/runs/${run}/${command}`, {
    headers: await writeHeaders(page, key),
    data: { expected_version: expectedVersion },
  });
}

/**
 * Cancels the run unless it has ended, so a test leaves no run for the worker. Terminal states
 * come from the shared run vocabulary.
 */
export async function cancelUnlessTerminal(
  page: Page,
  run: string,
): Promise<void> {
  const summary = await readRun(page, run);
  if (isTerminal(summary.status)) return;
  await runCommand(page, {
    run,
    command: "cancel",
    expectedVersion: summary.version,
    key: `cancel-${run}`,
  });
}
