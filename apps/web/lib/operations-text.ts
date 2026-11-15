/**
 * Operations' words for the local status (PRD-Studio OP-01, OP-02 and OP-04, Decision 0022 D5,
 * WSYS-05, WSYS-10): each check's sentence and measured value, the verdict's counts, the facts, the
 * history and each route's qualification. Tables are keyed by the contract's unions, so a check or
 * state the contract gains fails the type check here (WSYS-09). Pure and JSX-free, so `node --test`
 * covers it.
 */
import type {
  DelayedOccurrence,
  LocalStatus,
  OperationCondition,
  QueueStatus,
  RestoreRecord,
  RouteQualification,
} from "@autobots/api-client";

import { formatInstant } from "./format.ts";
import { counted } from "./plural.ts";
import { schemaValue } from "./schema-value.ts";

export type CheckName = OperationCondition["name"];
type Values = LocalStatus["values"];

/** Said in place of the status to a member, since Operations is the owner's (PRD-Studio OP-01). */
export const OWNER_ONLY = "Only the workspace owner can see Operations.";

const CONDITIONS: Readonly<Record<string, string>> = {
  database_ready: "The database is answering.",
  database_unreachable: "The database isn't answering. New work is refused.",
  database_not_configured: "No database is configured.",
  schema_ready: "The schema has what this version needs.",
  schema_behind: "Migrations are behind this version. New work is refused.",
  schema_ahead:
    "This database is newer than this version. New work still runs.",
  schema_unknown: "The schema can't be checked without the database.",
  no_hold: "Nothing is holding work.",
  restore_hold:
    "This instance was restored. All work is held until an operator releases it.",
  hold_unknown: "Holds can't be checked without the database.",
  adapter_qualified: "The checkpoint adapter is qualified for this release.",
  adapter_unqualified:
    "This release's checkpoint adapter isn't qualified. Saved work and new work wait.",
  adapter_unknown: "The adapter can't be checked without the database.",
  storage_ready: "Storage is answering.",
  storage_unreachable: "Storage isn't answering. New work is refused.",
  storage_not_configured: "No Storage is configured. New work is refused.",
  disk_ready: "The disk has room.",
  disk_low: "The disk is low. New work is refused until there's room.",
  disk_unreadable: "The disk couldn't be checked. New work is refused.",
  queue_ready: "No job has lost its worker.",
  leases_expired: "A job lost its worker. It waits for the next one.",
  worker_ready: "A worker is running.",
  worker_absent: "No worker is running. Queued work waits.",
  no_inference_worker:
    "Queued work needs a worker that can call a model, and none is running.",
};

/** A check's sentence for its code. A code this page doesn't know is shown as sent. */
export function conditionText(code: string): string {
  return CONDITIONS[code] ?? code;
}

export const CHECK_LABEL: Readonly<Record<CheckName, string>> = {
  database: "Database",
  schema: "Schema",
  hold: "Hold",
  adapter: "Checkpoints",
  storage: "Storage",
  disk: "Disk",
  queue: "Queue",
  worker: "Worker",
};

const HOLDS: Readonly<Record<string, string>> = {
  no_hold: "no hold",
  restore_hold: "held after a restore",
  hold_unknown: "hold unknown",
};

const UNKNOWN_HOLD = "hold unknown";

/** The verdict's hold, from the hold check's code, or unknown when there's none. */
export function holdText(conditions: readonly OperationCondition[]): string {
  const hold = conditions.find((item) => item.name === "hold");
  return HOLDS[hold?.code ?? "hold_unknown"] ?? UNKNOWN_HOLD;
}

/** OP-01: how many of the checks shown pass. */
export function passingText(conditions: readonly OperationCondition[]): string {
  const passing = conditions.filter((item) => item.state === "ok").length;
  return `${passing} of ${conditions.length} checks pass`;
}

export function workersText(workers: number | null): string {
  return workers === null
    ? "workers unknown"
    : counted(workers, "worker", "workers");
}

export function verdictText(ready: boolean): string {
  return ready
    ? "Ready. New work can start."
    : "Not ready. New work is refused until this clears.";
}

const integer = new Intl.NumberFormat("en");
const gigabytes = new Intl.NumberFormat("en", { maximumFractionDigits: 1 });

export function formatGigabytes(bytes: number): string {
  return `${gigabytes.format(bytes / 1_000_000_000)} GB`;
}

// One reader per check, so each stays a small expression. Numbers only (Decision 0022 D5).
const VALUES: Readonly<Record<CheckName, (values: Values) => string | null>> = {
  database: (values) =>
    values.database_p95_ms === null
      ? "No probe timed yet."
      : `p95 ${values.database_p95_ms} ms over the last ${values.database_probes} probes.`,
  schema: (values) =>
    schemaValue(values.applied_migrations, values.shipped_migrations),
  // The package and its release. Its name holds the database's, so the page names it plainly.
  adapter: (values) =>
    `LangGraph checkpoint adapter ${values.checkpoint_adapter.split(" ").at(-1) ?? ""}.`,
  storage: (values) =>
    values.storage_bytes === null
      ? null
      : `${integer.format(values.storage_bytes)} bytes in published artifacts.`,
  disk: ({ disk_free_bytes: free, disk_total_bytes: total }) =>
    free === null || total === null
      ? null
      : `${formatGigabytes(free)} free of ${formatGigabytes(total)}.`,
  queue: ({ leased_jobs: leased, queued_jobs: queued }) =>
    leased === null || queued === null
      ? null
      : `${leased} leased, ${queued} queued.`,
  worker: (values) =>
    values.workers === null ? null : `${workersText(values.workers)}.`,
  hold: () => null,
};

/** PRD-Studio OP-02: a check's measured value, when one exists. */
export function checkValue(name: CheckName, values: Values): string | null {
  return VALUES[name](values);
}

export function tracingText(tracing: LocalStatus["remote_tracing"]): string {
  return `Remote tracing: ${
    tracing === "disabled"
      ? "off. Logs stay on this Mac."
      : "on. Check this process's environment."
  }`;
}

export function backupText(hours: number | null): string {
  return `Last backup: ${
    hours === null
      ? "none found in the configured directory."
      : `${counted(hours, "hour", "hours")} ago.`
  }`;
}

const OPENROUTER: Readonly<Record<LocalStatus["openrouter"], string>> = {
  available:
    "OpenRouter's catalog answered. That says nothing about your key or a model call.",
  unavailable:
    "OpenRouter can't be reached. Local work and this page keep working, and new model calls wait.",
  unknown:
    "not checked, as provider settings aren't configured for this process.",
};

export function openrouterText(state: LocalStatus["openrouter"]): string {
  return `OpenRouter: ${OPENROUTER[state]}`;
}

export function catalogTimeText(ms: number): string {
  return `The catalog answered in ${ms} ms.`;
}

export function loopbackText(loopbackOnly: boolean | null): string {
  if (loopbackOnly === null) return "Network: not determined in this process.";
  return loopbackOnly
    ? "Network: the API listens on this Mac's loopback only."
    : "Network: the API listens beyond loopback. Check how it was started.";
}

export function queueText(queue: QueueStatus | null): string {
  return queue === null
    ? "Workspace counts need the database, so they aren't shown."
    : `Jobs in this workspace: ${queue.queued} queued, ${queue.claimed} running, ${queue.expired_leases} lost their worker.`;
}

function spaced(code: string): string {
  return code.replaceAll("_", " ");
}

export function delayedText(occurrence: DelayedOccurrence): string {
  const reason =
    occurrence.reason === null ? "" : `, ${spaced(occurrence.reason)}`;
  return `${occurrence.routine}: ${spaced(occurrence.status)} at ${formatInstant(occurrence.occurrence_time)}${reason}`;
}

export function restoreText(restore: RestoreRecord): string {
  const checks = `${restore.checks_passed} of ${restore.checks_total} checks`;
  const result =
    restore.result === "passed"
      ? `verified, ${checks}`
      : restore.result === "failed"
        ? `verification failed, ${checks}`
        : "restored, and not verified";
  return `${formatInstant(restore.at)}: ${result}`;
}

export function routeStatusText(route: RouteQualification): string {
  return route.status === "qualified_with_limits"
    ? `Tested ${route.qualified_on}, with limits.`
    : "Not qualified.";
}
