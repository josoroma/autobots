/**
 * The suites' `test`, with pages and contexts that close when a test ends, whatever its outcome
 * (TWEB-02, TWEB-16), and helper processes that stop with it (TWEB-11). Role pages sign in through
 * the form before the test body starts; `signedInPage` signs in where the test calls it. Each
 * fixture hands its value to Playwright's callback, named `provide` here rather than `use`, which
 * the React hooks lint would read as a hook.
 */
import {
  test as base,
  type BrowserContext,
  type BrowserContextOptions,
  type Page,
} from "@playwright/test";

import { signIn, users, type Credentials } from "./auth.ts";
import { streamDbHelper, type DbHelperStream } from "./db-helpers.ts";

export { expect } from "@playwright/test";

export type StartDbStream = (
  name: string,
  args: readonly string[],
  env?: Record<string, string>,
) => DbHelperStream;

interface SupportFixtures {
  /** A context of its own, with the configuration's options and any given here. */
  openContext: (options?: BrowserContextOptions) => Promise<BrowserContext>;
  /** A page in a context of its own. */
  openPage: (options?: BrowserContextOptions) => Promise<Page>;
  /** A page in a context of its own, signed in through the form as `user`. */
  signedInPage: (user: Credentials) => Promise<Page>;
  /** Workspace A's owner, signed in. */
  asOwner: Page;
  /** Workspace B's owner, signed in. */
  asOwnerB: Page;
  /** A member of workspace A who isn't its owner, signed in. */
  asMember: Page;
  /** A member of workspace A only, signed in. */
  asReader: Page;
  /** Starts a tests/db helper that keeps running. It's stopped when the test ends. */
  dbStream: StartDbStream;
}

async function signedIn(
  openPage: (options?: BrowserContextOptions) => Promise<Page>,
  user: Credentials,
): Promise<Page> {
  const page = await openPage();
  await signIn(page, user);
  return page;
}

export const test = base.extend<SupportFixtures>({
  openContext: async ({ browser }, provide) => {
    const opened: BrowserContext[] = [];
    await provide(async (options = {}) => {
      const context = await browser.newContext(options);
      opened.push(context);
      return context;
    });
    for (const context of opened) await context.close();
  },
  openPage: async ({ openContext }, provide) => {
    await provide(async (options) => (await openContext(options)).newPage());
  },
  signedInPage: async ({ openPage }, provide) => {
    await provide((user) => signedIn(openPage, user));
  },
  asOwner: async ({ openPage }, provide) => {
    await provide(await signedIn(openPage, users.owner));
  },
  asOwnerB: async ({ openPage }, provide) => {
    await provide(await signedIn(openPage, users.ownerB));
  },
  asMember: async ({ openPage }, provide) => {
    await provide(await signedIn(openPage, users.member));
  },
  asReader: async ({ openPage }, provide) => {
    await provide(await signedIn(openPage, users.reader));
  },
  dbStream: async ({}, provide) => {
    const started: DbHelperStream[] = [];
    await provide((name, args, env) => {
      const stream = streamDbHelper(name, args, env);
      started.push(stream);
      return stream;
    });
    for (const stream of started) stream.stop();
  },
});
