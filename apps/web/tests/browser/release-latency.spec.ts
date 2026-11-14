import { writeFileSync } from "node:fs";

import { csrfToken } from "./support/api.ts";
import { signIn, users } from "./support/auth.ts";
import { optional } from "./support/env.ts";
import { expect, test } from "./support/fixtures.ts";
import { admitRun } from "./support/runs.ts";

// US-10.1's timing, run only by scripts/qualify_release.py --ui, against the real API and web app with
// the worker stopped. The clock starts before the cancel is sent, so it overstates the time since the
// event was committed, and stops on the first frame after the event reaches the page.
const SAMPLES = 40;

test("a committed event reaches the page", async ({ page }) => {
  test.setTimeout(240_000);
  await signIn(page, users.owner);
  const csrf = await csrfToken(page);
  const timed: { ack_ms: number; shown_ms: number }[] = [];
  for (let index = 0; index < SAMPLES; index += 1) {
    const id = await admitRun(
      page,
      { goal_text: `Latency ${index}`, limit_micro_usd: 1000 },
      { key: `latency-${index}` },
    );
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
    optional("AUTOBOTS_RELEASE_LATENCY_OUT", "release-latency.json"),
    JSON.stringify(timed),
  );
});
