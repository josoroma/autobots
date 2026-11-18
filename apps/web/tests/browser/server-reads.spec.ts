import type { Page } from "@playwright/test";

import { addSessionCookie } from "./support/auth.ts";
import { arranged, webOrigin } from "./support/env.ts";
import { expect, test } from "./support/fixtures.ts";

// R-67: pages that read on the server, with the BFF's per-request session and workspace, show why a
// read failed in their first HTML, under the page's own title (XWEB-19). A read on the server can't
// be arranged with page.route, so these reach each state for real, in the web project that
// scripts/qualify_web.py arranges: no session, a session the API refuses, a person in no workspace,
// a chosen workspace the person isn't in, a name the API doesn't know, and a web server whose API
// is closed. Its API has no database, so a database read is unavailable there too. The out-of-date
// state, which no running service answers, is pinned in tests/unit/load-failure.test.ts.
const stack = arranged({
  unavailable: "AUTOBOTS_WEB_UNAVAILABLE_URL",
  internal: "AUTOBOTS_TEST_INTERNAL_TOKEN",
  sessionA: "AUTOBOTS_TEST_SESSION_A",
  sessionB: "AUTOBOTS_TEST_SESSION_B",
  forged: "AUTOBOTS_TEST_SESSION_FORGED",
});

const MISSING_RUN = "c0000000-0000-4000-8000-000000000001";
const MISSING_SESSION = "d0000000-0000-4000-8000-000000000001";
// A well-formed workspace ID that the arranged membership doesn't hold, as a stale choice would be.
const FOREIGN_WORKSPACE = "f0000000-0000-4000-8000-00000000000f";

interface ServerPage {
  path: string;
  title: string;
  /** What the page reads, as its failure sentences name it. */
  what: string;
}

const PAGES: readonly ServerPage[] = [
  { path: "/runs", title: "Runs", what: "runs" },
  {
    path: `/runs/${MISSING_RUN}/inspector`,
    title: "Run inspector",
    what: "this run",
  },
  {
    path: "/settings/data",
    title: "Data on this Mac",
    what: "the retention summary",
  },
  {
    path: `/sessions/${MISSING_SESSION}`,
    title: "Session",
    what: "this session",
  },
  { path: "/tools/calculate", title: "Tool", what: "this tool" },
];

// Home reads what needs the person only once their session is read, so a signed-out visitor sees its
// account section say so instead.
const HOME: ServerPage = {
  path: "/",
  title: "What should we work on?",
  what: "what needs you and recent runs",
};

function capitalized(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function unavailableWords(what: string): string {
  return `${capitalized(what)} can't be read right now. Check that the local services are running, then try again.`;
}

// The page's own server read. Home's composer shows its own client reads' states beside it.
const stateOf = (page: Page) =>
  page
    .getByRole("main")
    .locator('[data-read="server"] [data-state="unavailable"]');

/**
 * Opens the page, after checking that its first HTML already holds the state and no server key. The
 * page's h1 shows whatever the read did.
 */
async function openServerPage(
  page: Page,
  origin: string,
  { path, title }: ServerPage,
  reason: string,
): Promise<void> {
  const html = await (await page.request.get(`${origin}${path}`)).text();
  expect(html).toContain(`data-reason="${reason}"`);
  expect(html).not.toContain(stack.internal);
  await page.goto(`${origin}${path}`);
  await expect(
    page.getByRole("heading", { level: 1, name: title, exact: true }),
  ).toBeVisible();
  await expect(stateOf(page)).toHaveAttribute("data-reason", reason);
  // Nothing the read would have shown is there, such as Home's Needs you and Recent runs.
  await expect(
    page.locator('[data-field="needs-you"], [data-field="recent-runs"]'),
  ).toHaveCount(0);
}

test("the arranged values are present", () => {
  for (const value of Object.values(stack)) expect(value).not.toBe("");
});

test("a page read on the server tells a signed-out visitor to sign in, from its first HTML", async ({
  page,
}) => {
  for (const [who, session] of [
    ["no session", null],
    ["a session the API refuses", stack.forged],
  ] as const) {
    await page.context().clearCookies();
    if (session !== null) await addSessionCookie(page, session);
    for (const server of PAGES) {
      await test.step(`${server.path}, ${who}`, async () => {
        await openServerPage(page, webOrigin(), server, "signed_out");
        const state = stateOf(page);
        await expect(state.getByRole("alert")).toHaveText(
          `You're signed out. Sign in to see ${server.what}.`,
        );
        await expect(
          state.getByRole("link", { name: "Sign in" }),
        ).toHaveAttribute("href", "/sign-in");
        await expect(state.getByRole("button", { name: "Retry" })).toHaveCount(
          0,
        );
      });
    }
    await test.step(`${HOME.path}, ${who}`, async () => {
      await page.goto(HOME.path);
      await expect(
        page.getByRole("heading", { level: 1, name: HOME.title, exact: true }),
      ).toBeVisible();
      // Home's account section says so and offers Sign in, and nothing that needs the person shows.
      await expect(page.locator('[data-session="signed-out"]')).toHaveText(
        "You are not signed in.",
      );
      await expect(
        page
          .locator('[data-account-action="true"]')
          .getByRole("link", { name: "Sign in" }),
      ).toHaveAttribute("href", "/sign-in");
      await expect(
        page.locator('[data-field="needs-you"], [data-field="recent-runs"]'),
      ).toHaveCount(0);
    });
  }
});

test("a page read on the server shows the service's refusal in its words, with no Retry", async ({
  page,
}) => {
  for (const [who, session, workspace, words] of [
    ["a person in no workspace", stack.sessionB, null, "Choose a workspace."],
    [
      "a chosen workspace the person isn't in",
      stack.sessionA,
      FOREIGN_WORKSPACE,
      "This workspace is not available.",
    ],
  ] as const) {
    await page.context().clearCookies();
    await addSessionCookie(page, session);
    if (workspace !== null)
      await page.context().addCookies([
        {
          name: "autobots.workspace",
          value: workspace,
          url: webOrigin(),
          httpOnly: true,
          sameSite: "Strict",
        },
      ]);
    for (const server of [...PAGES, HOME]) {
      await test.step(`${server.path}, ${who}`, async () => {
        await openServerPage(page, webOrigin(), server, "denied");
        const state = stateOf(page);
        await expect(state.getByRole("alert")).toHaveText(words);
        await expect(state.getByRole("button", { name: "Retry" })).toHaveCount(
          0,
        );
        await expect(state.getByRole("link", { name: "Sign in" })).toHaveCount(
          0,
        );
      });
    }
  }
});

test("a page read on the server says when what it names isn't there", async ({
  page,
}) => {
  await addSessionCookie(page, stack.sessionA);
  for (const [server, words] of [
    [
      { path: "/runs/not-a-run/inspector", title: "Run inspector" },
      "That run is not available. Sign in with access to it, or check the link.",
    ],
    [
      { path: "/sessions/not-a-session", title: "Session" },
      "That session is not available.",
    ],
    [
      { path: "/tools/not_a_tool", title: "Tool" },
      "That tool isn't in the catalog.",
    ],
    // The API takes a search of up to 200 characters, and refuses a longer one as a 422.
    [
      { path: `/runs?q=${"x".repeat(201)}`, title: "Runs" },
      "Runs can't be found.",
    ],
  ] as const) {
    await test.step(server.path.slice(0, 40), async () => {
      await openServerPage(
        page,
        webOrigin(),
        { ...server, what: "" },
        "not_found",
      );
      const state = stateOf(page);
      await expect(state.getByRole("alert")).toHaveText(words);
      await expect(state.getByRole("button", { name: "Retry" })).toHaveCount(0);
    });
  }
});

test("a page read on the server says when the service is down, and Retry reads it again on the server", async ({
  page,
}) => {
  await addSessionCookie(page, stack.sessionA, stack.unavailable);
  // The closed API fails every page's read. Home reads its session first, which needs no database,
  // so it's opened on the arranged API, where its database reads are unavailable.
  for (const [origin, server] of [
    ...PAGES.map((item) => [stack.unavailable, item] as const),
    [webOrigin(), HOME] as const,
  ]) {
    await test.step(`${server.path} on ${origin}`, async () => {
      await openServerPage(page, origin, server, "unavailable");
      const state = stateOf(page);
      await expect(state.getByRole("alert")).toHaveText(
        unavailableWords(server.what),
      );
      await expect(state.getByRole("link", { name: "Sign in" })).toHaveCount(0);
      const retry = state.getByRole("button", { name: "Retry" });
      const pathname = new URL(server.path, origin).pathname;
      const reread = page.waitForRequest(
        (request) =>
          request.headers()["rsc"] === "1" &&
          new URL(request.url()).pathname === pathname,
      );
      await retry.click();
      await reread;
      // The service is still down, so the page says so again, and Retry is offered again.
      await expect(stateOf(page)).toHaveAttribute("data-reason", "unavailable");
      await expect(
        stateOf(page).getByRole("button", { name: "Retry" }),
      ).toBeEnabled();
    });
  }
  // Retry shows what the read answers now. Here the session changes before it is pressed, so the
  // outage gives way to the refusal the API sends that person.
  await test.step("Retry replaces the outage with the new answer", async () => {
    await page.goto(`${webOrigin()}${HOME.path}`);
    await expect(stateOf(page)).toHaveAttribute("data-reason", "unavailable");
    await page.context().clearCookies();
    await addSessionCookie(page, stack.sessionB);
    await stateOf(page).getByRole("button", { name: "Retry" }).click();
    await expect(stateOf(page)).toHaveAttribute("data-reason", "denied");
    await expect(stateOf(page).getByRole("alert")).toHaveText(
      "Choose a workspace.",
    );
  });
});

// React moves a streamed section into place in batches, so its streamed HTML can wait, hidden, before
// the reveal. Holding that reveal, as a busy browser can, shows whether anything renders the section
// again meanwhile: it must show once. next-themes reading a light Mac after mount used to do that,
// through its context, until its provider stopped wrapping the app (lib/theme-choice.ts).
test("a section read on the server shows once while its streamed HTML waits to be revealed", async ({
  openPage,
}) => {
  const page = await openPage({ colorScheme: "light" });
  await page.addInitScript(() => {
    const frame = window.requestAnimationFrame.bind(window);
    window.requestAnimationFrame = (callback) =>
      window.setTimeout(() => frame(callback), 1500);
  });
  await addSessionCookie(page, stack.sessionA);
  for (const [path, selector] of [
    ["/runs", '[data-group="needs_you"]'],
    ["/settings/data", '[data-state="unavailable"]'],
  ] as const) {
    await test.step(path, async () => {
      await page.goto(path);
      const section = page.locator(selector);
      await expect(section).toBeVisible();
      // Counted once, as it shows: a retry would look after a hidden copy had gone.
      expect(await section.count()).toBe(1);
      await expect(page.locator('div[hidden][id^="S:"]')).toHaveCount(0);
    });
  }
});
