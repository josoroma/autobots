import { expect, test } from "@playwright/test";

const ORIGIN = process.env.AUTOBOTS_WEB_URL ?? "";
const API = process.env.AUTOBOTS_API_URL ?? "";
const UNAVAILABLE = process.env.AUTOBOTS_WEB_UNAVAILABLE_URL ?? "";
const INTERNAL = process.env.AUTOBOTS_TEST_INTERNAL_TOKEN ?? "";
const SESSION_A = process.env.AUTOBOTS_TEST_SESSION_A ?? "";
const SESSION_B = process.env.AUTOBOTS_TEST_SESSION_B ?? "";
const SESSION_FORGED = process.env.AUTOBOTS_TEST_SESSION_FORGED ?? "";
const TOKEN_A = process.env.AUTOBOTS_TEST_TOKEN_A ?? "";
const WORKSPACE_A = process.env.AUTOBOTS_TEST_WORKSPACE_A ?? "";
const path = `/api/v1/workspaces/${WORKSPACE_A}`;

function session(token: string): { Cookie: string } {
  return { Cookie: `autobots.session=${token}` };
}

test("the arranged values are present", () => {
  for (const value of [
    ORIGIN,
    API,
    UNAVAILABLE,
    INTERNAL,
    SESSION_A,
    SESSION_B,
    WORKSPACE_A,
  ]) {
    expect(value).not.toBe("");
  }
});

test("a member reaches its workspace through the BFF, with the generated contract's shape", async ({
  request,
}) => {
  const reply = await request.get(path, { headers: session(SESSION_A) });
  expect(reply.status()).toBe(200);
  expect(await reply.json()).toEqual({ schema_version: 1, id: WORKSPACE_A });
});

test("another workspace's member is refused", async ({ request }) => {
  const reply = await request.get(path, { headers: session(SESSION_B) });
  expect(reply.status()).toBe(403);
  expect((await reply.json()).code).toBe("forbidden");
});

test("no session and a forged session are refused", async ({ request }) => {
  expect((await request.get(path)).status()).toBe(401);
  const forged = await request.get(path, { headers: session(SESSION_FORGED) });
  expect(forged.status()).toBe(401);
});

test("a forged origin or host is refused before the API", async ({
  request,
}) => {
  const origin = await request.get(path, {
    headers: { ...session(SESSION_A), Origin: "http://evil.example" },
  });
  expect(origin.status()).toBe(403);
  const host = await request.get(path, {
    headers: { ...session(SESSION_A), Host: "evil.example" },
  });
  expect(host.status()).toBe(403);
  expect((await host.json()).code).toBe("forbidden_host");
});

test("a write needs the origin and CSRF token", async ({ request }) => {
  const headers = { ...session(SESSION_A), Origin: ORIGIN };
  const missing = await request.post(path, { headers });
  expect(missing.status()).toBe(403);
  expect((await missing.json()).code).toBe("missing_csrf");
  const mismatched = await request.post(path, {
    headers: {
      ...headers,
      Cookie: `${headers.Cookie}; autobots.csrf=one`,
      "X-Autobots-CSRF": "two",
    },
  });
  expect((await mismatched.json()).code).toBe("invalid_csrf");
});

test("a valid write reaches the API, which has no such route", async ({
  request,
}) => {
  const token = await (await request.get("/api/csrf")).json();
  const reply = await request.post(path, {
    headers: {
      Cookie: `autobots.session=${SESSION_A}; autobots.csrf=${token.token}`,
      Origin: ORIGIN,
      [token.header]: token.token,
    },
  });
  expect(reply.status()).toBe(405);
});

test("a client's own internal header is dropped, and cannot replace a session", async ({
  request,
}) => {
  const reply = await request.get(path, {
    headers: { "X-Autobots-Internal": "client-value" },
  });
  expect(reply.status()).toBe(401);
});

test("the Python API refuses a request without the internal credential", async ({
  request,
}) => {
  const url = `${API}/v1/workspaces/${WORKSPACE_A}`;
  const bearer = { Authorization: `Bearer ${TOKEN_A}` };
  expect((await request.get(url, { headers: bearer })).status()).toBe(401);
  expect(
    (
      await request.get(url, {
        headers: { ...bearer, "X-Autobots-Internal": "forged" },
      })
    ).status(),
  ).toBe(401);
  const valid = await request.get(url, {
    headers: { ...bearer, "X-Autobots-Internal": INTERNAL },
  });
  expect(valid.status()).toBe(200);
  const health = await request.get(`${API}/v1/health`);
  expect(health.status()).toBe(401);
});

test("the Python API refuses a forged host", async ({ request }) => {
  const reply = await request.get(`${API}/v1/health`, {
    headers: { Host: "evil.example", "X-Autobots-Internal": INTERNAL },
  });
  expect(reply.status()).toBe(400);
});

test("errors expose no credential or stack", async ({ request }) => {
  for (const reply of [
    await request.get(path),
    await request.get(path, { headers: session(SESSION_B) }),
  ]) {
    const text = await reply.text();
    expect(text).not.toContain(INTERNAL);
    expect(text).not.toContain("Traceback");
    expect(text).not.toContain("127.0.0.1");
  }
});

test("no privileged value reaches the browser", async ({ page }) => {
  const bodies: string[] = [];
  page.on("response", async (response) => {
    if (response.url().startsWith(ORIGIN)) {
      bodies.push(await response.text().catch(() => ""));
    }
  });
  await page.goto("/");
  await page.waitForLoadState("networkidle");
  expect(bodies.length).toBeGreaterThan(1);
  for (const body of bodies) {
    expect(body).not.toContain(INTERNAL);
    expect(body).not.toContain("AUTOBOTS_INTERNAL_TOKEN");
  }
  expect(
    await page.evaluate(() =>
      Object.keys(window).filter((name) => /autobots_/i.test(name)),
    ),
  ).toEqual([]);
});

test("an unavailable API is a visible, safe state", async ({ page }) => {
  await page.goto(`${UNAVAILABLE}/`);
  const status = page.getByRole("status");
  await expect(status).toContainText("Python API: unavailable");
  expect(await page.locator("body").innerText()).not.toContain("ECONNREFUSED");
  const reply = await page.request.get(`${UNAVAILABLE}${path}`, {
    headers: session(SESSION_A),
  });
  expect(reply.status()).toBe(503);
  expect((await reply.json()).code).toBe("service_unavailable");
  await page.screenshot({
    path: `${process.env.AUTOBOTS_WEB_SCREENSHOTS ?? "test-results/screenshots"}/api-unavailable.png`,
  });
});

test("US-14.1: a member reads the tool catalog through the BFF, and nothing else does", async ({
  request,
}) => {
  const reply = await request.get("/api/v1/tools", {
    headers: session(SESSION_A),
  });
  expect(reply.status()).toBe(200);
  const catalog = await reply.json();
  expect(catalog.schema_version).toBe(1);
  expect(catalog.catalog_digest).toMatch(/^[0-9a-f]{64}$/);
  const ids = catalog.tools.map(
    (tool: { tool_id: string; version: number }) =>
      `${tool.tool_id}@${tool.version}`,
  );
  expect(new Set(ids).size).toBe(ids.length);
  expect(ids).toEqual(
    expect.arrayContaining(["calculate@1", "create_github_issue@2"]),
  );
  const browse = catalog.tools.find(
    (tool: { tool_id: string }) => tool.tool_id === "browse_goal",
  );
  expect(browse).toMatchObject({
    registered: false,
    availability: "disabled_by_policy",
    grantable_to: [],
  });
  const github = catalog.tools.find(
    (tool: { tool_id: string }) => tool.tool_id === "create_github_issue",
  );
  expect(github.key_requirement.variables).toEqual([
    "GITHUB_REPOSITORY",
    "GITHUB_TOKEN",
  ]);
  expect(github.availability).toBe("key_missing");
  const version = await request.get("/api/v1/tools/calculate/versions/1", {
    headers: session(SESSION_A),
  });
  expect((await version.json()).input_schema.properties.operation.enum).toEqual(
    ["sum", "mean", "min", "max"],
  );
  expect((await request.get("/api/v1/tools")).status()).toBe(401);
  expect(
    (
      await request.get("/api/v1/tools", { headers: session(SESSION_B) })
    ).status(),
  ).toBe(403);
});

// R-19: one double-submit token per browser session, so overlapping writes can't refuse each other.
test("overlapping CSRF requests return the session's one token", async ({
  request,
}) => {
  const first = await (await request.get("/api/csrf")).json();
  const [a, b] = await Promise.all([
    request.get("/api/csrf"),
    request.get("/api/csrf"),
  ]);
  expect((await a.json()).token).toBe(first.token);
  expect((await b.json()).token).toBe(first.token);
});

// R-19 step 1: once the session has its token, two writes that overlap each fetch it, as csrfFetch
// in two tabs would, then both are sent. A token minted per fetch would refuse the first, and one
// per session lets both through. Validation changes nothing, so the writes leave no trace.
test("two overlapping writes both succeed with the session's one CSRF token", async ({
  page,
}) => {
  await page
    .context()
    .addCookies([{ name: "autobots.session", value: SESSION_A, url: ORIGIN }]);
  await page.goto("/");
  const replies = await page.evaluate(async () => {
    const graph = {
      nodes: [
        { id: "in", block: "input", version: 1, config: { type: "string" } },
        { id: "out", block: "output", version: 1 },
      ],
      links: [
        {
          source: "in",
          source_port: "value",
          target: "out",
          target_port: "value",
        },
      ],
    };
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
  });
  // A refused token would be a 403 with invalid_csrf; both reach the API and are answered.
  expect(replies.map((reply) => [reply.status, reply.code])).toEqual([
    [200, undefined],
    [200, undefined],
  ]);
  expect(replies[1]?.token).toBe(replies[0]?.token);
});
