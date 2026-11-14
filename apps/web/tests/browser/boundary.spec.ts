import {
  parseToolCatalog,
  parseToolDescriptor,
  parseWorkspaceSummary,
} from "@autobots/api-client";

import { expectRefusal, readCsrfToken } from "./support/api.ts";
import { addSessionCookie } from "./support/auth.ts";
import { arranged, need, screenshotPath, webOrigin } from "./support/env.ts";
import { inToOut } from "./support/builders.ts";
import { expect, test } from "./support/fixtures.ts";
import { captureBodies } from "./support/leaks.ts";

// Arranged by scripts/qualify_web.py, which mints the sessions and passes the addresses.
const stack = arranged({
  api: "AUTOBOTS_API_URL",
  unavailable: "AUTOBOTS_WEB_UNAVAILABLE_URL",
  internal: "AUTOBOTS_TEST_INTERNAL_TOKEN",
  sessionA: "AUTOBOTS_TEST_SESSION_A",
  sessionB: "AUTOBOTS_TEST_SESSION_B",
  sessionForged: "AUTOBOTS_TEST_SESSION_FORGED",
  tokenA: "AUTOBOTS_TEST_TOKEN_A",
  workspaceA: "AUTOBOTS_TEST_WORKSPACE_A",
});
const workspacePath = () => `/api/v1/workspaces/${stack.workspaceA}`;
const SIGN_IN_UNAVAILABLE =
  "Signing in is unavailable right now. Check that the local services are running, then try again.";

function session(token: string): { Cookie: string } {
  return { Cookie: `autobots.session=${token}` };
}

test("the arranged values are present", () => {
  for (const name of [
    "AUTOBOTS_WEB_URL",
    "AUTOBOTS_API_URL",
    "AUTOBOTS_WEB_UNAVAILABLE_URL",
    "AUTOBOTS_TEST_INTERNAL_TOKEN",
    "AUTOBOTS_TEST_SESSION_A",
    "AUTOBOTS_TEST_SESSION_B",
    "AUTOBOTS_TEST_WORKSPACE_A",
  ]) {
    expect(need(name)).not.toBe("");
  }
});

test("a member reaches its workspace through the BFF, with the generated contract's shape", async ({
  request,
}) => {
  const reply = await request.get(workspacePath(), {
    headers: session(stack.sessionA),
  });
  expect(reply.status()).toBe(200);
  const body: unknown = await reply.json();
  expect(parseWorkspaceSummary(body)).toEqual({
    schema_version: 1,
    id: stack.workspaceA,
  });
});

test("another workspace's member is refused", async ({ request }) => {
  const reply = await request.get(workspacePath(), {
    headers: session(stack.sessionB),
  });
  await expectRefusal(reply, { status: 403, code: "forbidden" });
});

test("no session and a forged session are refused", async ({ request }) => {
  expect((await request.get(workspacePath())).status()).toBe(401);
  const forged = await request.get(workspacePath(), {
    headers: session(stack.sessionForged),
  });
  expect(forged.status()).toBe(401);
});

test("a forged origin or host is refused before the API", async ({
  request,
}) => {
  const origin = await request.get(workspacePath(), {
    headers: { ...session(stack.sessionA), Origin: "http://evil.example" },
  });
  expect(origin.status()).toBe(403);
  const host = await request.get(workspacePath(), {
    headers: { ...session(stack.sessionA), Host: "evil.example" },
  });
  await expectRefusal(host, { status: 403, code: "forbidden_host" });
});

test("a write needs the origin and CSRF token", async ({ request }) => {
  const headers = { ...session(stack.sessionA), Origin: webOrigin() };
  const missing = await request.post(workspacePath(), { headers });
  await expectRefusal(missing, { status: 403, code: "missing_csrf" });
  const mismatched = await request.post(workspacePath(), {
    headers: {
      ...headers,
      Cookie: `${headers.Cookie}; autobots.csrf=one`,
      "X-Autobots-CSRF": "two",
    },
  });
  await expectRefusal(mismatched, { status: 403, code: "invalid_csrf" });
});

test("a valid write reaches the API, which has no such route", async ({
  request,
}) => {
  const token = await readCsrfToken(request);
  const reply = await request.post(workspacePath(), {
    headers: {
      Cookie: `autobots.session=${stack.sessionA}; autobots.csrf=${token.token}`,
      Origin: webOrigin(),
      [token.header]: token.token,
    },
  });
  expect(reply.status()).toBe(405);
});

test("a client's own internal header is dropped, and cannot replace a session", async ({
  request,
}) => {
  const reply = await request.get(workspacePath(), {
    headers: { "X-Autobots-Internal": "client-value" },
  });
  expect(reply.status()).toBe(401);
});

test("the Python API refuses a request without the internal credential", async ({
  request,
}) => {
  const url = `${stack.api}/v1/workspaces/${stack.workspaceA}`;
  const bearer = { Authorization: `Bearer ${stack.tokenA}` };
  expect((await request.get(url, { headers: bearer })).status()).toBe(401);
  expect(
    (
      await request.get(url, {
        headers: { ...bearer, "X-Autobots-Internal": "forged" },
      })
    ).status(),
  ).toBe(401);
  const valid = await request.get(url, {
    headers: { ...bearer, "X-Autobots-Internal": stack.internal },
  });
  expect(valid.status()).toBe(200);
  const health = await request.get(`${stack.api}/v1/health`);
  expect(health.status()).toBe(401);
});

test("the Python API refuses a forged host", async ({ request }) => {
  const reply = await request.get(`${stack.api}/v1/health`, {
    headers: { Host: "evil.example", "X-Autobots-Internal": stack.internal },
  });
  expect(reply.status()).toBe(400);
});

test("errors expose no credential or stack", async ({ request }) => {
  for (const reply of [
    await request.get(workspacePath()),
    await request.get(workspacePath(), { headers: session(stack.sessionB) }),
  ]) {
    const text = await reply.text();
    expect(text).not.toContain(stack.internal);
    expect(text).not.toContain("Traceback");
    expect(text).not.toContain("127.0.0.1");
  }
});

test("no privileged value reaches the browser", async ({ page }) => {
  const origin = webOrigin();
  const bodies = captureBodies(page, (response) =>
    response.url().startsWith(origin),
  );
  await page.goto("/");
  await page.waitForLoadState("networkidle");
  const read = await bodies();
  expect(read.length).toBeGreaterThan(1);
  for (const reply of read) {
    expect(reply.body, reply.url).not.toContain(stack.internal);
    expect(reply.body, reply.url).not.toContain("AUTOBOTS_INTERNAL_TOKEN");
  }
  expect(
    await page.evaluate(() =>
      Object.keys(window).filter((name) => /autobots_/i.test(name)),
    ),
  ).toEqual([]);
});

test("an unavailable API is a visible, safe state", async ({ page }) => {
  await page.goto(`${stack.unavailable}/`);
  const status = page.getByRole("status");
  await expect(status).toContainText("Python API: unavailable");
  expect(await page.locator("body").innerText()).not.toContain("ECONNREFUSED");
  const reply = await page.request.get(
    `${stack.unavailable}${workspacePath()}`,
    { headers: session(stack.sessionA) },
  );
  await expectRefusal(reply, { status: 503, code: "service_unavailable" });
  await page.screenshot({ path: screenshotPath("api-unavailable.png") });
});

// A session read that fails for any reason but a 401 is unavailable, never signed out (WSHL-02).
test("a session the API cannot read shows the account as unavailable, not Sign in", async ({
  page,
}) => {
  await addSessionCookie(page, stack.sessionA, stack.unavailable);
  await page.goto(`${stack.unavailable}/`);
  await expect(page.locator('[data-account-state="unavailable"]')).toHaveText(
    /Account unavailable/,
  );
  await expect(page.locator('[data-session="unavailable"]')).toBeVisible();
  await expect(page.getByRole("link", { name: "Sign in" })).toHaveCount(0);
  await expect(page.getByText("You are not signed in.")).toHaveCount(0);
  // Signing out needs only the sign-in service, so it stays offered (PRD-Studio SH-05).
  await expect(
    page.getByRole("button", { name: "Sign out" }).first(),
  ).toBeVisible();
  expect(await page.locator("body").innerText()).not.toContain("ECONNREFUSED");
  await page.screenshot({ path: screenshotPath("session-unavailable.png") });
});

test("choosing a workspace while the API is unavailable is a 503, not a sign-in prompt", async ({
  request,
}) => {
  const token = await readCsrfToken(request, `${stack.unavailable}/api/csrf`);
  const reply = await request.post(`${stack.unavailable}/api/workspace`, {
    headers: {
      Cookie: `autobots.session=${stack.sessionA}; autobots.csrf=${token.token}`,
      Origin: stack.unavailable,
      [token.header]: token.token,
    },
    data: { workspace_id: stack.workspaceA },
  });
  await expectRefusal(reply, { status: 503, code: "service_unavailable" });
});

// scripts/qualify_web.py arranges the Auth address as a closed port, so these reach a real Auth
// outage through the session route (WSHL-07).
test("an unreachable sign-in service is reported as unavailable, not as a wrong password", async ({
  page,
  request,
}) => {
  const email = "member@example.test";
  const password = "never-echoed-password";
  const token = await readCsrfToken(request);
  const reply = await request.post("/api/session", {
    headers: {
      Cookie: `autobots.csrf=${token.token}`,
      Origin: webOrigin(),
      [token.header]: token.token,
    },
    data: { email, password },
  });
  const text = await reply.text();
  expect(text).not.toContain(password);
  expect(text).not.toContain(email);
  await expectRefusal(reply, { status: 503, code: "auth_unavailable" });
  await page.goto("/sign-in");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText(SIGN_IN_UNAVAILABLE)).toBeVisible();
  await expect(
    page.getByText("That email and password did not work."),
  ).toHaveCount(0);
});

test("signing out with the sign-in service unreachable still ends the session on this device", async ({
  page,
}) => {
  await addSessionCookie(page, stack.sessionA);
  const token = await readCsrfToken(page.request);
  const reply = await page.request.delete("/api/session", {
    headers: { Origin: webOrigin(), [token.header]: token.token },
  });
  expect(reply.status()).toBe(200);
  expect(
    (await page.context().cookies()).some(
      (cookie) => cookie.name === "autobots.session",
    ),
  ).toBe(false);
});

test("US-14.1: a member reads the tool catalog through the BFF, and nothing else does", async ({
  request,
}) => {
  const reply = await request.get("/api/v1/tools", {
    headers: session(stack.sessionA),
  });
  expect(reply.status()).toBe(200);
  const catalog = parseToolCatalog(await reply.json());
  expect(catalog.schema_version).toBe(1);
  expect(catalog.catalog_digest).toMatch(/^[0-9a-f]{64}$/);
  const ids = catalog.tools.map((tool) => `${tool.tool_id}@${tool.version}`);
  expect(new Set(ids).size).toBe(ids.length);
  expect(ids).toEqual(
    expect.arrayContaining(["calculate@1", "create_github_issue@2"]),
  );
  const browse = catalog.tools.find((tool) => tool.tool_id === "browse_goal");
  expect(browse).toMatchObject({
    registered: false,
    availability: "disabled_by_policy",
    grantable_to: [],
  });
  const github = catalog.tools.find(
    (tool) => tool.tool_id === "create_github_issue",
  );
  expect(github?.key_requirement?.variables).toEqual([
    "GITHUB_REPOSITORY",
    "GITHUB_TOKEN",
  ]);
  expect(github?.availability).toBe("key_missing");
  const version = await request.get("/api/v1/tools/calculate/versions/1", {
    headers: session(stack.sessionA),
  });
  expect(version.status()).toBe(200);
  const descriptor = parseToolDescriptor(await version.json());
  expect(descriptor.input_schema).toMatchObject({
    properties: { operation: { enum: ["sum", "mean", "min", "max"] } },
  });
  expect((await request.get("/api/v1/tools")).status()).toBe(401);
  expect(
    (
      await request.get("/api/v1/tools", { headers: session(stack.sessionB) })
    ).status(),
  ).toBe(403);
});

// R-19: one double-submit token per browser session, so overlapping writes can't refuse each other.
test("overlapping CSRF requests return the session's one token", async ({
  request,
}) => {
  const first = await readCsrfToken(request);
  const [a, b] = await Promise.all([
    readCsrfToken(request),
    readCsrfToken(request),
  ]);
  expect(a.token).toBe(first.token);
  expect(b.token).toBe(first.token);
});

// R-19 step 1: once the session has its token, two writes that overlap each fetch it, as csrfFetch
// in two tabs would, then both are sent. A token minted per fetch would refuse the first, and one
// per session lets both through. Validation changes nothing, so the writes leave no trace.
test("two overlapping writes both succeed with the session's one CSRF token", async ({
  page,
}) => {
  await addSessionCookie(page, stack.sessionA);
  await page.goto("/");
  const replies = await page.evaluate(async (graph) => {
    await fetch("/api/csrf", { cache: "no-store" });
    const tokens: { header: string; token: string }[] = await Promise.all(
      [0, 1].map(async () =>
        (await fetch("/api/csrf", { cache: "no-store" })).json(),
      ),
    );
    return Promise.all(
      tokens.map(async ({ header, token }) => {
        const reply = await fetch("/api/v1/workflows/validate", {
          method: "POST",
          headers: { "Content-Type": "application/json", [header]: token },
          body: JSON.stringify(graph),
        });
        return { status: reply.status, token, code: (await reply.json()).code };
      }),
    );
  }, inToOut());
  // A refused token would be a 403 with invalid_csrf; both reach the API and are answered.
  expect(replies.map((reply) => [reply.status, reply.code])).toEqual([
    [200, undefined],
    [200, undefined],
  ]);
  expect(replies[1]?.token).toBe(replies[0]?.token);
});
