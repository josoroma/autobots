import { parseArtifactList } from "@autobots/api-client";

import { getJson, expectRefusal } from "./support/api.ts";
import { signIn, users } from "./support/auth.ts";
import { arranged } from "./support/env.ts";
import { expect, test } from "./support/fixtures.ts";

const fixture = arranged({
  run: "AUTOBOTS_TEST_ARTIFACT_RUN",
  artifact: "AUTOBOTS_TEST_ARTIFACT_ID",
  text: "AUTOBOTS_TEST_ARTIFACT_TEXT",
  gone: "AUTOBOTS_TEST_ARTIFACT_GONE",
  tampered: "AUTOBOTS_TEST_ARTIFACT_TAMPERED",
});

test("a member lists a run's artifacts and downloads the verified bytes", async ({
  page,
}) => {
  await signIn(page, users.owner);
  const listed = await getJson(page, {
    path: `/api/v1/runs/${fixture.run}/artifacts`,
    parse: parseArtifactList,
  });
  expect(listed.artifacts).toHaveLength(1);
  expect(listed.artifacts[0]?.id).toBe(fixture.artifact);
  expect(listed.artifacts[0]?.status).toBe("published");
  expect(JSON.stringify(listed)).not.toContain("object_path");
  const download = await page.request.get(
    `/api/v1/artifacts/${fixture.artifact}/download`,
  );
  expect(download.status()).toBe(200);
  expect(await download.text()).toBe(fixture.text);
  expect(download.headers()["content-disposition"]).toContain("attachment");
  expect(download.headers()["x-content-type-options"]).toBe("nosniff");
  expect(download.headers()["cache-control"]).toContain("no-store");
});

test("another workspace sees nothing and downloads nothing", async ({
  page,
}) => {
  await signIn(page, users.ownerB);
  const listed = await getJson(page, {
    path: `/api/v1/runs/${fixture.run}/artifacts`,
    parse: parseArtifactList,
  });
  expect(listed.artifacts).toEqual([]);
  const download = await page.request.get(
    `/api/v1/artifacts/${fixture.artifact}/download`,
  );
  expect(download.status()).toBe(404);
  expect(await download.text()).not.toContain(fixture.text);
});

test("a missing or altered object is reported and never served", async ({
  page,
}) => {
  await signIn(page, users.owner);
  for (const id of [fixture.gone, fixture.tampered]) {
    await expectRefusal(
      await page.request.get(`/api/v1/artifacts/${id}/download`),
      { status: 409, code: "artifact_missing" },
    );
  }
});

test("a signed-out request gets no bytes", async ({ request }) => {
  const download = await request.get(
    `/api/v1/artifacts/${fixture.artifact}/download`,
  );
  expect(download.status()).toBe(401);
  expect(await download.text()).not.toContain(fixture.text);
});
