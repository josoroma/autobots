import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { mkdirSync, readdirSync, rmSync, writeFileSync } from "node:fs";

// US-15.18, PRD-Studio OP-01, OP-02 and OP-04. scripts/qualify_identity.py arranges the ops-n workspace:
// one job that lost its worker, one leased and one queued that no worker may take, and published
// artifacts of 1,000 and 2,345 bytes. tests/db/operations_live.py adds two live worker heartbeats.
const OPS_EMAIL = process.env.AUTOBOTS_TEST_OPS_EMAIL ?? "";
const OPS_PASSWORD = process.env.AUTOBOTS_TEST_OPS_PASSWORD ?? "";
const EMAIL_A = process.env.AUTOBOTS_TEST_OWNER_EMAIL ?? "";
const PASSWORD_A = process.env.AUTOBOTS_TEST_OWNER_PASSWORD ?? "";
const BACKUPS = process.env.AUTOBOTS_TEST_BACKUP_DIR ?? "";
// Decision 0022 D5's values, exactly.
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
  "storage_bytes",
  "workers",
];
const MIGRATIONS = readdirSync("../../supabase/migrations").filter((name) =>
  /^\d{14}_[a-z0-9_]+\.sql$/.test(name),
).length;

test.describe.configure({ mode: "serial" });

function heartbeats(action: "start" | "stop"): { live: number } {
  const printed = execFileSync(
    process.env.AUTOBOTS_TEST_PYTHON ?? "",
    [process.env.AUTOBOTS_TEST_OPS_HELPER ?? "", action],
    {
      env: {
        ...process.env,
        AUTOBOTS_DATABASE_URL: process.env.AUTOBOTS_TEST_RUNTIME_URL ?? "",
        PYTHONPATH: process.env.AUTOBOTS_TEST_PYTHONPATH ?? "",
      },
      encoding: "utf8",
    },
  );
  return JSON.parse(printed.trim().split("\n").at(-1) ?? "{}");
}

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

test.beforeAll(() => {
  expect(OPS_EMAIL, "the ops-n workspace is arranged").not.toBe("");
  expect(heartbeats("start").live).toBe(2);
});

// A later suite expects no worker, so the two stop whatever happens here.
test.afterAll(() => {
  heartbeats("stop");
});

test("the verdict counts the checks shown, two workers and the hold, and each check shows its value", async ({
  page,
}) => {
  await signIn(page, OPS_EMAIL, OPS_PASSWORD);
  // At least 20 readiness probes, so the database time is a p95 over a full window.
  for (let probe = 0; probe < 20; probe += 1) {
    const reply = await page.request.get("/api/v1/readiness");
    expect(reply.status()).toBe(200);
  }
  heartbeats("start");
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
    `${MIGRATIONS} migrations applied.`,
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
  const scan = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(scan.violations).toEqual([]);
});

test("the status response holds D5's values only, with no path or secret, and tracing off", async ({
  page,
}) => {
  await signIn(page, OPS_EMAIL, OPS_PASSWORD);
  const reply = await page.request.get("/api/v1/operations/local-status");
  expect(reply.status()).toBe(200);
  const body = await reply.json();
  expect(Object.keys(body.values).sort()).toEqual(D5);
  const values = JSON.stringify(body.values);
  for (const leak of ["/", "\\", "127.0.0.1", "localhost", "sk-or-", "eyJ"])
    expect(values).not.toContain(leak);
  const whole = JSON.stringify(body);
  for (const leak of [
    "/Users/",
    "/private/",
    "127.0.0.1",
    "postgres://",
    "postgresql://",
    "sk-or-",
    "eyJ",
  ])
    expect(whole).not.toContain(leak);
  expect(body.remote_tracing).toBe("disabled");
  expect(body.values.disk_free_bytes).toBeLessThanOrEqual(
    body.values.disk_total_bytes,
  );
});

test("the delayed schedules, backups, restores, tracing, model routes and retention still show", async ({
  page,
}) => {
  mkdirSync(`${BACKUPS}/arranged-values`, { recursive: true });
  writeFileSync(
    `${BACKUPS}/arranged-values/manifest.json`,
    JSON.stringify({
      created_at: new Date(Date.now() - 3 * 3_600_000).toISOString(),
    }),
  );
  writeFileSync(
    `${BACKUPS}/arranged-values/restores.jsonl`,
    `${JSON.stringify({ at: "2026-11-07T09:00:00+00:00", result: "passed", checks_passed: 12, checks_total: 12 })}\n`,
  );
  try {
    await signIn(page, EMAIL_A, PASSWORD_A);
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
    rmSync(`${BACKUPS}/arranged-values`, { recursive: true });
  }
});
