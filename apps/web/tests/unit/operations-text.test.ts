/**
 * Pins Operations' words (PRD-Studio OP-01, OP-02 and OP-04, Decision 0022 D5, WSYS-05, WSYS-10):
 * each check's sentence and measured value, the verdict's counts, the facts, the history and each
 * route's qualification. The operations browser suites read several of these sentences exactly.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import type { LocalStatus, OperationCondition } from "@autobots/api-client";

import {
  backupText,
  catalogTimeText,
  CHECK_LABEL,
  checkValue,
  conditionText,
  delayedText,
  formatGigabytes,
  holdText,
  loopbackText,
  openrouterText,
  passingText,
  queueText,
  restoreText,
  routeStatusText,
  tracingText,
  verdictText,
  workersText,
} from "../../lib/operations-text.ts";
import { counted } from "../../lib/plural.ts";

type Values = LocalStatus["values"];

const VALUES: Values = {
  applied_migrations: 54,
  catalog_fetch_ms: 120,
  checkpoint_adapter: "langgraph-checkpoint-postgres 2.0.21",
  database_p95_ms: 4,
  database_probes: 20,
  disk_free_bytes: 123_400_000_000,
  disk_total_bytes: 500_000_000_000,
  leased_jobs: 1,
  loopback_only: true,
  queued_jobs: 1,
  shipped_migrations: 54,
  storage_bytes: 3_345,
  workers: 2,
};

function condition(
  name: OperationCondition["name"],
  state: OperationCondition["state"],
  code: string,
): OperationCondition {
  return { name, state, code };
}

test("a count takes its singular noun for exactly one", () => {
  assert.equal(counted(0, "worker", "workers"), "0 workers");
  assert.equal(counted(1, "worker", "workers"), "1 worker");
  assert.equal(counted(2, "worker", "workers"), "2 workers");
});

test("each check's value is the measured number, or nothing when none was measured", () => {
  assert.equal(
    checkValue("database", VALUES),
    "p95 4 ms over the last 20 probes.",
  );
  assert.equal(
    checkValue("database", { ...VALUES, database_p95_ms: null }),
    "No probe timed yet.",
  );
  assert.equal(checkValue("schema", VALUES), "54 of 54 migrations applied.");
  assert.equal(
    checkValue("adapter", VALUES),
    "LangGraph checkpoint adapter 2.0.21.",
  );
  assert.equal(
    checkValue("storage", VALUES),
    "3,345 bytes in published artifacts.",
  );
  assert.equal(checkValue("storage", { ...VALUES, storage_bytes: null }), null);
  assert.equal(checkValue("disk", VALUES), "123.4 GB free of 500 GB.");
  assert.equal(checkValue("disk", { ...VALUES, disk_total_bytes: null }), null);
  assert.equal(checkValue("queue", VALUES), "1 leased, 1 queued.");
  assert.equal(checkValue("queue", { ...VALUES, queued_jobs: null }), null);
  assert.equal(checkValue("worker", VALUES), "2 workers.");
  assert.equal(checkValue("worker", { ...VALUES, workers: 1 }), "1 worker.");
  assert.equal(checkValue("worker", { ...VALUES, workers: null }), null);
  assert.equal(checkValue("hold", VALUES), null);
});

test("gigabytes keep one decimal at most", () => {
  assert.equal(formatGigabytes(1_000_000_000), "1 GB");
  assert.equal(formatGigabytes(1_250_000_000), "1.3 GB");
  assert.equal(formatGigabytes(12_345_000_000_000), "12,345 GB");
});

test("every check has a label, and a code the page doesn't know is shown as sent", () => {
  assert.equal(CHECK_LABEL.adapter, "Checkpoints");
  assert.equal(Object.keys(CHECK_LABEL).length, 8);
  assert.equal(conditionText("database_ready"), "The database is answering.");
  assert.equal(
    conditionText("leases_expired"),
    "A job lost its worker. It waits for the next one.",
  );
  assert.equal(conditionText("something_new"), "something_new");
});

test("the verdict counts the checks shown, the workers and the hold", () => {
  const conditions = [
    condition("database", "ok", "database_ready"),
    condition("queue", "degraded", "leases_expired"),
    condition("hold", "ok", "no_hold"),
  ];
  assert.equal(passingText(conditions), "2 of 3 checks pass");
  assert.equal(holdText(conditions), "no hold");
  assert.equal(
    holdText([condition("hold", "unavailable", "restore_hold")]),
    "held after a restore",
  );
  assert.equal(holdText([]), "hold unknown");
  assert.equal(holdText([condition("hold", "ok", "new_code")]), "hold unknown");
  assert.equal(workersText(2), "2 workers");
  assert.equal(workersText(1), "1 worker");
  assert.equal(workersText(null), "workers unknown");
  assert.equal(verdictText(true), "Ready. New work can start.");
  assert.equal(
    verdictText(false),
    "Not ready. New work is refused until this clears.",
  );
});

test("the facts read as the suites expect, with one hour singular", () => {
  assert.equal(
    tracingText("disabled"),
    "Remote tracing: off. Logs stay on this Mac.",
  );
  assert.equal(
    tracingText("enabled"),
    "Remote tracing: on. Check this process's environment.",
  );
  assert.equal(backupText(3), "Last backup: 3 hours ago.");
  assert.equal(backupText(1), "Last backup: 1 hour ago.");
  assert.equal(
    backupText(null),
    "Last backup: none found in the configured directory.",
  );
  assert.match(
    openrouterText("available"),
    /^OpenRouter: OpenRouter's catalog answered\./,
  );
  assert.match(openrouterText("unavailable"), /OpenRouter can't be reached/);
  assert.match(openrouterText("unknown"), /^OpenRouter: not checked/);
  assert.equal(catalogTimeText(120), "The catalog answered in 120 ms.");
  assert.equal(
    loopbackText(true),
    "Network: the API listens on this Mac's loopback only.",
  );
  assert.match(loopbackText(false), /beyond loopback/);
  assert.equal(loopbackText(null), "Network: not determined in this process.");
  assert.equal(
    queueText({
      queued: 3,
      claimed: 1,
      expired_leases: 0,
      oldest_queued_seconds: 9,
    }),
    "Jobs in this workspace: 3 queued, 1 running, 0 lost their worker.",
  );
  assert.equal(
    queueText(null),
    "Workspace counts need the database, so they aren't shown.",
  );
});

test("a delayed occurrence, a restore and a route each read in one line", () => {
  assert.equal(
    delayedText({
      routine: "Nightly report",
      status: "skipped_overlap",
      occurrence_time: "2026-11-05T02:00:00+00:00",
      reason: "host_away",
    }),
    "Nightly report: skipped overlap at 2026-11-05T02:00:00.000Z, host away",
  );
  assert.equal(
    delayedText({
      routine: "Nightly report",
      status: "missed",
      occurrence_time: "2026-11-05T02:00:00+00:00",
      reason: null,
    }),
    "Nightly report: missed at 2026-11-05T02:00:00.000Z",
  );
  const at = "2026-11-06T12:00:00+00:00";
  const record = { at, checks_passed: 14, checks_total: 14 };
  assert.equal(
    restoreText({ ...record, result: "passed" }),
    "2026-11-06T12:00:00.000Z: verified, 14 of 14 checks",
  );
  assert.equal(
    restoreText({ ...record, checks_passed: 12, result: "failed" }),
    "2026-11-06T12:00:00.000Z: verification failed, 12 of 14 checks",
  );
  assert.equal(
    restoreText({
      at,
      checks_passed: null,
      checks_total: null,
      result: "not_verified",
    }),
    "2026-11-06T12:00:00.000Z: restored, and not verified",
  );
  const route = {
    canonical_id: "openai/gpt-6.1-terra",
    configuration: null,
    limits: null,
    profile: "openrouter_terra" as const,
    qualified_on: "2026-11-05",
  };
  assert.equal(
    routeStatusText({ ...route, status: "qualified_with_limits" }),
    "Tested 2026-11-05, with limits.",
  );
  assert.equal(
    routeStatusText({ ...route, status: "not_qualified" }),
    "Not qualified.",
  );
});
