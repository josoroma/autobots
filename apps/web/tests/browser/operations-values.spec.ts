import { mkdirSync, readdirSync, rmSync, writeFileSync } from "node:fs";

import { parseLocalStatus } from "@autobots/api-client";

import { expectNoA11yViolations, WCAG_22_AA } from "./support/a11y.ts";
import { getJson } from "./support/api.ts";
import { signIn, users } from "./support/auth.ts";
import { need } from "./support/env.ts";
import { objectOf, runDbHelper } from "./support/db-helpers.ts";
import { expect, test } from "./support/fixtures.ts";
import { expectNoPrivateValues } from "./support/leaks.ts";

// US-15.18, PRD-Studio OP-01, OP-02 and OP-04. scripts/qualify_identity.py arranges the ops-n workspace:
// one job that lost its worker, one leased and one queued that no worker may take, and published
// artifacts of 1,000 and 2,345 bytes. tests/db/operations_live.py adds two live worker heartbeats.
// Decision 0022 D5's values, exactly, and Decision 0023 E2's shipped count.
const D5 = [
  "applied_migrations",
  "catalog_fetch_ms",
  "checkpoint_adapter",
  "database_p95_ms",
  "database_probes",
  "disk_free_bytes",
  "disk_total_bytes",
  "leased_jobs",
  "loopback_only",
  "queued_jobs",
  "shipped_migrations",
  "storage_bytes",
  "workers",
];
const MIGRATIONS = readdirSync("../../supabase/migrations").filter((name) =>
  /^\d{14}_[a-z0-9_]+\.sql$/.test(name),
).length;

test.describe.configure({ mode: "serial" });

function heartbeats(action: "start" | "stop"): Promise<{ live: number }> {
  return runDbHelper(
    "operations_live.py",
    [action],
    objectOf({ live: "number" }),
  );
}

test.beforeAll(async () => {
  // The ops-n workspace is arranged, or this names the variable that's missing.
  need("AUTOBOTS_TEST_OPS_EMAIL");
  expect((await heartbeats("start")).live).toBe(2);
});

// operations.spec.ts, after this file, expects no worker, so the two stop whatever happens here.
test.afterAll(async () => {
  await heartbeats("stop");
});

test("the verdict counts the checks shown, two workers and the hold, and each check shows its value", async ({
  page,
}) => {
  await signIn(page, users.ops);
  // At least 20 readiness probes, so the database time is a p95 over a full window.
  for (let probe = 0; probe < 20; probe += 1) {
    const reply = await page.request.get("/api/v1/readiness");
    expect(reply.status()).toBe(200);
  }
  await heartbeats("start");
  await page.goto("/operations");
  await expect(page.getByText("Ready. New work can start.")).toBeVisible();
  const checks = page.locator('[data-field="checks"] > li');
  await expect(checks).toHaveCount(8);
  const passing = await page
    .locator('[data-field="checks"] > li[data-state="ok"]')
    .count();
  expect(passing).toBe(7);
  await expect(
    page.locator('[data-field="checks"] > li[data-state="degraded"]'),
  ).toContainText("A job lost its worker.");
  await expect(page.locator('[data-field="checks-passing"]')).toHaveText(
    `${passing} of 8 checks pass`,
  );
  await expect(page.locator('[data-field="workers"]')).toHaveText("2 workers");
  await expect(page.locator('[data-field="hold"]')).toHaveText("no hold");

  await expect(page.locator('[data-field="value-database"]')).toHaveText(
    /^p95 \d+ ms over the last 20 probes\.$/,
  );
  await expect(page.locator('[data-field="value-schema"]')).toHaveText(
    `${MIGRATIONS} of ${MIGRATIONS} migrations applied.`,
  );
  await expect(page.locator('[data-field="value-storage"]')).toHaveText(
    "3,345 bytes in published artifacts.",
  );
  await expect(page.locator('[data-field="value-disk"]')).toHaveText(
    /^[\d,.]+ GB free of [\d,.]+ GB\.$/,
  );
  await expect(page.locator('[data-field="value-queue"]')).toHaveText(
    "1 leased, 1 queued.",
  );
  await expect(page.locator('[data-field="value-adapter"]')).toHaveText(
    /^LangGraph checkpoint adapter \d+\.\d+[\w.+-]*\.$/,
  );
  await expect(page.locator('[data-field="value-worker"]')).toHaveText(
    "2 workers.",
  );
  await expect(page.locator('[data-field="catalog-time"]')).toHaveText(
    /^ The catalog answered in \d+ ms\.$/,
  );
  await expect(page.locator('[data-field="loopback"]')).toContainText(
    "the API listens on this Mac's loopback only.",
  );
  await expectNoA11yViolations(page, { extraTags: WCAG_22_AA });
});

test("the status response holds D5's values only, with no path or secret, and tracing off", async ({
  page,
}) => {
  await signIn(page, users.ops);
  const body = await getJson(page, {
    path: "/api/v1/operations/local-status",
    parse: parseLocalStatus,
  });
  expect(Object.keys(body.values).sort()).toEqual(D5);
  // The values hold no path at all, so neither separator may appear.
  expectNoPrivateValues(JSON.stringify(body.values), {
    label: "the values",
    extra: ["/", "\\"],
  });
  expectNoPrivateValues(JSON.stringify(body), { label: "the status" });
  expect(body.remote_tracing).toBe("disabled");
  const { disk_free_bytes: free, disk_total_bytes: total } = body.values;
  expect(
    free !== null && total !== null && free <= total,
    `${free} of ${total} bytes free`,
  ).toBe(true);
});

test("the delayed schedules, backups, restores, tracing, model routes and retention still show", async ({
  page,
}) => {
  const backup = `${need("AUTOBOTS_TEST_BACKUP_DIR")}/arranged-values`;
  mkdirSync(backup, { recursive: true });
  writeFileSync(
    `${backup}/manifest.json`,
    JSON.stringify({
      created_at: new Date(Date.now() - 3 * 3_600_000).toISOString(),
    }),
  );
  writeFileSync(
    `${backup}/restores.jsonl`,
    `${JSON.stringify({ at: "2026-11-07T09:00:00+00:00", result: "passed", checks_passed: 12, checks_total: 12 })}\n`,
  );
  try {
    await signIn(page, users.owner);
    await page.goto("/operations");
    await expect(page.locator('[data-field="delayed"]')).toContainText(
      "Arranged nightly report",
    );
    await expect(page.getByText("Last backup: 3 hours ago.")).toBeVisible();
    await expect(page.locator('[data-field="restores"]')).toContainText(
      "verified, 12 of 12 checks",
    );
    await expect(page.getByText(/Remote tracing: off/)).toBeVisible();
    await expect(page.locator("[data-operations-route]").first()).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Retention" }),
    ).toBeVisible();
    await expect(page.locator('[data-field="checks-passing"]')).toHaveText(
      /^\d+ of \d+ checks pass$/,
    );
  } finally {
    rmSync(backup, { recursive: true });
  }
});
