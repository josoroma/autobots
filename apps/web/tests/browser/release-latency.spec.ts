import { writeFileSync } from "node:fs";
import { expect, test } from "@playwright/test";

// US-10.1's timing, run only by scripts/qualify_release.py --ui, against the real API and web app with
// the worker stopped. The clock starts before the cancel is sent, so it overstates the time since the
// event was committed, and stops on the first frame after the event reaches the page.
const SAMPLES = 40;

test("a committed event reaches the page", async ({ page }) => {
  test.setTimeout(240_000);
  await page.goto("/sign-in");
  await page
    .getByLabel("Email")
    .fill(process.env.AUTOBOTS_TEST_OWNER_EMAIL ?? "");
  await page
    .getByLabel("Password")
    .fill(process.env.AUTOBOTS_TEST_OWNER_PASSWORD ?? "");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText(/Signed in, with access to/)).toBeVisible();
  const csrf = await (await page.request.get("/api/csrf")).json();
  const timed: { ack_ms: number; shown_ms: number }[] = [];
  for (let index = 0; index < SAMPLES; index += 1) {
    const reply = await page.request.post("/api/v1/runs", {
      headers: {
        [csrf.header]: csrf.token,
        Origin: new URL(page.url()).origin,
        "Content-Type": "application/json",
        "Idempotency-Key": `latency-${index}`,
      },
      data: { goal_text: `Latency ${index}`, limit_micro_usd: 1000 },
    });
    expect(reply.status()).toBe(202);
    const id = (await reply.json()).run_id as string;
    await page.goto(`/runs/${id}`);
    await expect(page.locator("[data-connection]")).toHaveAttribute(
      "data-connection",
      "live",
    );
    const sample = await page.evaluate(
      async ({ id, header, token, key }) => {
        const count = () => document.querySelectorAll("[data-sequence]").length;
        const before = count();
        const shown = new Promise<number>((resolve) => {
          const observer = new MutationObserver(() => {
            if (count() > before) {
              observer.disconnect();
              requestAnimationFrame(() => resolve(performance.now()));
            }
          });
          observer.observe(document.body, { subtree: true, childList: true });
          setTimeout(() => resolve(-1), 10_000);
        });
        const began = performance.now();
        const answer = await fetch(`/api/v1/runs/${id}/cancel`, {
          method: "POST",
          headers: {
            [header]: token,
            "Content-Type": "application/json",
            "Idempotency-Key": key,
          },
          body: JSON.stringify({ expected_version: 1 }),
        });
        const acknowledged = performance.now();
        const at = await shown;
        return {
          status: answer.status,
          ack_ms: acknowledged - began,
          shown_ms: at < 0 ? -1 : at - began,
        };
      },
      { id, header: csrf.header, token: csrf.token, key: `cancel-${index}` },
    );
    expect(sample.status).toBe(200);
    expect(sample.shown_ms).toBeGreaterThan(0);
    timed.push({ ack_ms: sample.ack_ms, shown_ms: sample.shown_ms });
  }
  writeFileSync(
    process.env.AUTOBOTS_RELEASE_LATENCY_OUT ?? "release-latency.json",
    JSON.stringify(timed),
  );
});
