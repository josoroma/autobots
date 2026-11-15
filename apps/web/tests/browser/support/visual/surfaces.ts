/**
 * The screens the visual walk captures in both themes, and the DS-03 names it doesn't capture,
 * each with its reason (US-11.11, TWEB-03, TWEB-09). Every page route under app/ is a surface here
 * or listed in ABSENT_ROUTES, which the walk checks.
 */
import { expect, type Page } from "@playwright/test";

export const THEMES = ["dark", "light"] as const;
export type Theme = (typeof THEMES)[number];

/** Who the surface is opened as: no one, workspace A's owner, or an owner with no provider key. */
export type SurfaceContext = "signed-out" | "owner" | "no-key";

/** What arrangeSurfaces made for the surfaces to show. */
export interface SurfaceIds {
  run: string;
  expert: string;
  session: string;
  workflow: string;
  execution: string;
}

export interface Surface {
  /** Names the step, the result and the screenshot, `<name>-<theme>.png`. */
  name: string;
  context: SurfaceContext;
  path: (ids: SurfaceIds) => string;
  /** Runs before the page opens, such as a route that holds or refuses a read. */
  arrange?: (page: Page) => Promise<unknown>;
  /** Resolves once the page shows what it's captured for. */
  ready: (page: Page) => Promise<void>;
}

// DS-03's names that this walk doesn't capture, each with its reason, written into results.json.
export const ABSENT = {
  onboarding:
    "No separate flow. Key setup on Models is what a new owner meets, and it's captured as key-setup.",
  "dialogs and portals":
    "Not walked. The Tools page's guide (Decision 0026 G2), Search and About are native modal dialogs, which make main inert, and this walk's keyboard, focus and hover probes read main. tools.spec.ts scans the guide with axe in both themes, appearance.spec.ts checks About's surface in both themes, and search.spec.ts checks Search by keyboard. No portals; selects are native.",
  menus: "None apart from native selects, whose open lists the OS draws.",
  notifications:
    "No toast or notification surface. Results are inline status text, measured where they appear. Browser notifications are drawn by the OS, and their setting is captured as settings-notifications.",
  charts:
    "One chart, the jobs chart on Operations, whose series use the status color tokens rather than chart-1 to chart-5. It's captured on the operations surface, which waits for its plot.",
  "artifact previews":
    "Artifacts are downloaded through a link, and no preview exists. The list is captured on the run.",
  "file lists":
    "No screen lists a run's working files. Published artifacts are on the run.",
  "workflow canvas":
    "The editor is a validated text form, with no canvas, so no edge or node marker is drawn.",
};

/** Page routes, as app/ names them, that no surface opens, each with its reason. */
export const ABSENT_ROUTES: Readonly<Record<string, string>> = {};

const heading = (name: string | RegExp) => async (page: Page) => {
  await expect(page.getByRole("heading", { name }).first()).toBeVisible();
};

const shows = (selector: string) => async (page: Page) => {
  await expect(page.locator(selector)).toBeVisible();
};

const showsSome = (selector: string) => async (page: Page) => {
  await expect(page.locator(selector).first()).toBeVisible();
};

const labelled = (label: string) => async (page: Page) => {
  await expect(page.getByLabel(label)).toBeVisible();
};

const hang = (page: Page, pattern: string) =>
  page.route(pattern, () => undefined);

const refuse = (page: Page, pattern: string) =>
  page.route(pattern, (route) => route.abort());

export const SURFACES: readonly Surface[] = [
  {
    name: "sign-in",
    context: "signed-out",
    path: () => "/sign-in",
    ready: labelled("Email"),
  },
  {
    name: "key-setup",
    context: "no-key",
    path: () => "/settings/models",
    ready: labelled("API key"),
  },
  {
    name: "home",
    context: "owner",
    path: () => "/",
    ready: heading("New goal"),
  },
  {
    name: "runs",
    context: "owner",
    path: () => "/runs",
    ready: heading("Runs"),
  },
  {
    name: "run",
    context: "owner",
    path: (ids) => `/runs/${ids.run}`,
    ready: shows('[data-verification="passed"]'),
  },
  {
    name: "inspector",
    context: "owner",
    path: (ids) => `/runs/${ids.run}/inspector`,
    ready: showsSome("[data-call]"),
  },
  {
    name: "experts",
    context: "owner",
    path: () => "/experts",
    ready: heading("Experts"),
  },
  {
    name: "expert-editor",
    context: "owner",
    path: (ids) => `/experts/${ids.expert}`,
    ready: labelled("Instructions"),
  },
  {
    name: "session",
    context: "owner",
    path: (ids) => `/sessions/${ids.session}`,
    ready: shows('[data-disclosure="model"]'),
  },
  {
    name: "workflows",
    context: "owner",
    path: () => "/workflows",
    ready: heading("Workflows"),
  },
  {
    name: "workflow-editor",
    context: "owner",
    path: (ids) => `/workflows/${ids.workflow}`,
    ready: shows('[data-disclosure="model"]'),
  },
  {
    name: "workflow-monitor",
    context: "owner",
    path: (ids) => `/workflow-executions/${ids.execution}`,
    ready: async (page) => {
      await expect(page.locator("main")).not.toContainText("Loading");
    },
  },
  {
    name: "approvals",
    context: "owner",
    path: () => "/approvals",
    ready: showsSome("[data-approval]"),
  },
  {
    name: "approvals-empty",
    context: "no-key",
    path: () => "/approvals",
    ready: async (page) => {
      await expect(
        page.getByText("Nothing is waiting for a decision."),
      ).toBeVisible();
    },
  },
  {
    name: "settings",
    context: "owner",
    path: () => "/settings",
    ready: labelled("Dark"),
  },
  {
    name: "models",
    context: "owner",
    path: () => "/settings/models",
    ready: shows('[data-field="role-effect"]'),
  },
  {
    name: "operations",
    context: "owner",
    path: () => "/operations",
    ready: async (page) => {
      await heading("Operations")(page);
      await expect(
        page
          .locator('[data-field="jobs-chart"]')
          .getByRole("img", { name: /^Jobs per hour/ }),
      ).toBeVisible();
    },
  },
  // The Experts list reads in the browser, so a route can hold or refuse its read. The run list's
  // first page is read on the server (R-67), where no route reaches.
  {
    name: "state-loading",
    context: "owner",
    path: () => "/experts",
    arrange: (page) => hang(page, "**/api/v1/experts"),
    ready: shows('[data-state="loading"]'),
  },
  {
    name: "state-error",
    context: "owner",
    path: () => "/experts",
    arrange: (page) => refuse(page, "**/api/v1/experts"),
    ready: shows('[data-state="unavailable"]'),
  },
  {
    name: "state-empty",
    context: "no-key",
    path: () => "/workflows",
    ready: heading("Workflows"),
  },
  {
    name: "state-local-only",
    context: "owner",
    path: () => "/settings/models",
    arrange: (page) => refuse(page, "**/api/**"),
    ready: async (page) => {
      await expect(page.getByRole("alert").first()).toBeVisible();
    },
  },
  // Tools, a tool's page and five Settings sections (TWEB-09).
  {
    name: "tools",
    context: "owner",
    path: () => "/tools",
    ready: shows('[data-tool="calculate"]'),
  },
  {
    name: "tool-detail",
    context: "owner",
    path: () => "/tools/calculate",
    ready: shows('[data-guide="what"]'),
  },
  {
    name: "settings-notifications",
    context: "owner",
    path: () => "/settings/notifications",
    ready: shows('[data-field="notify-permission"]'),
  },
  {
    name: "settings-account",
    context: "owner",
    path: () => "/settings/account",
    ready: labelled("Display name"),
  },
  {
    name: "settings-data",
    context: "owner",
    path: () => "/settings/data",
    ready: shows('[data-field="run-retention"]'),
  },
  {
    name: "settings-keyboard",
    context: "owner",
    path: () => "/settings/keyboard",
    ready: showsSome("[data-shortcut]"),
  },
  {
    name: "settings-keys-and-vars",
    context: "owner",
    path: () => "/settings/keys-and-vars",
    ready: showsSome("[data-item]"),
  },
];
