import { expectRefusal, writeHeaders } from "./support/api.ts";
import { arranged } from "./support/env.ts";
import { expect, test } from "./support/fixtures.ts";
import { readRun } from "./support/runs.ts";

const unknown = arranged({
  run: "AUTOBOTS_TEST_UNKNOWN_RUN",
  operation: "AUTOBOTS_TEST_UNKNOWN_OPERATION",
});

test("an unknown effect is visible, blocks resume, and only an owner can resolve it", async ({
  asOwnerB,
  asMember,
  asOwner: page,
}) => {
  const reconcile = `/api/v1/runs/${unknown.run}/effects/${unknown.operation}/reconcile`;
  const foreign = await asOwnerB.request.post(reconcile, {
    headers: await writeHeaders(asOwnerB, "foreign"),
    data: { outcome: "delivered", evidence: "x", generation: 1 },
  });
  expect(foreign.status()).toBe(404);
  const denied = await asMember.request.post(reconcile, {
    headers: await writeHeaders(asMember, "member"),
    data: { outcome: "delivered", evidence: "x", generation: 1 },
  });
  expect(denied.status()).toBe(403);

  await page.goto(`/runs/${unknown.run}`);
  await expect(page.locator("[data-run-status]")).toHaveAttribute(
    "data-run-status",
    "paused",
  );
  await expect(page.locator("[data-stop-reason]")).toContainText(
    "outcome unknown",
  );
  const panel = page.locator("[data-unknown-effects]");
  await expect(panel).toContainText("send_blind");
  await expect(panel).toContainText("may or may not have happened");
  await expect(
    panel.getByRole("button", { name: "It happened" }),
  ).toBeDisabled();

  const { version } = await readRun(page, unknown.run);
  const early = await page.request.post(`/api/v1/runs/${unknown.run}/resume`, {
    headers: await writeHeaders(page, "early"),
    data: { expected_version: version },
  });
  const refused = await expectRefusal(early, { status: 409 });
  expect(["unknown_effect", "credentials_required"]).toContain(refused.code);

  await page.getByLabel("What you saw").fill("Seen in the destination log.");
  await panel.getByRole("button", { name: "It happened" }).click();
  await expect(page.locator("[data-unknown-effects]")).toHaveCount(0);
  await expect(
    page.locator("[data-sequence]").filter({ hasText: "reconciled" }),
  ).toHaveCount(1);
  const again = await page.request.post(reconcile, {
    headers: await writeHeaders(page, "again"),
    data: { outcome: "not_delivered", evidence: "changed", generation: 1 },
  });
  await expectRefusal(again, { status: 409, code: "operation_not_unknown" });
});
