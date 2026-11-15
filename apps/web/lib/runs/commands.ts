/**
 * A person's run commands (SP-010, R-49, WRUN-12). Which ones a run offers comes from the service,
 * as RunWorkspace.allowed_commands, computed with domain.next_status, so no screen re-derives the
 * command table (XMOD-06). This holds their words, their submit target, the body and the one POST
 * that sends them. Each caller passes the version it means: the run page reads the current one
 * before a press, and the runs list's panel sends the one it loaded (PRD-Studio RN-04). Runs in the
 * browser and under `node --test`.
 */
import {
  parseRunSummary,
  type RunCommandRequest,
  type RunWorkspace,
} from "@autobots/api-client";

import { csrfFetch } from "../csrf-fetch.ts";
import { loadJson, type LoadOptions } from "../load.ts";

export type RunCommand = RunWorkspace["allowed_commands"][number];

export const COMMAND_LABEL: Readonly<Record<RunCommand, string>> = {
  pause: "Pause",
  resume: "Resume",
  cancel: "Cancel run",
};

/** A command's target for the submit hook: the run for Pause and Resume, its own for Cancel. */
export function commandTarget(command: RunCommand): string {
  return command === "cancel" ? "cancel" : "";
}

/** The body of every command: the version the sender means, which the service checks. */
export function commandBody(expectedVersion: number): string {
  return JSON.stringify({
    expected_version: expectedVersion,
  } satisfies RunCommandRequest);
}

/**
 * One attempt at a command, with the key the submit hook holds until its outcome is known, so a
 * lost reply applies it once (Decision 0027 D2).
 */
export function sendRunCommand(
  runId: string,
  command: RunCommand,
  attempt: { key: string; body: string },
): Promise<Response> {
  return csrfFetch(`/api/v1/runs/${encodeURIComponent(runId)}/${command}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": attempt.key,
    },
    body: attempt.body,
  });
}

/**
 * The run's version now, as a worker moves it often, or `shown` when it can't be read. A stale one
 * is refused by the service, never applied.
 */
export async function currentVersion(
  runId: string,
  shown: number,
  options: LoadOptions = {},
): Promise<number> {
  const loaded = await loadJson(
    `/api/v1/runs/${encodeURIComponent(runId)}`,
    parseRunSummary,
    options,
  );
  return loaded.kind === "ready" ? loaded.value.version : shown;
}
