/**
 * Signing in, and the disposable roles the runners arrange (TWEB-02, TWEB-18). Each role's email
 * and password are read when a test first uses it, so a missing role fails with its variable's
 * name. Specs sign in through the real form, as identity.spec.ts must; boundary.spec.ts also sets
 * session cookies to test the request guard itself.
 */
import { expect, type Page } from "@playwright/test";

import { need, webOrigin } from "./env.ts";

export interface Credentials {
  email: string;
  password: string;
}

function role(prefix: string): Credentials {
  return {
    email: need(`${prefix}_EMAIL`),
    password: need(`${prefix}_PASSWORD`),
  };
}

/**
 * The roles by intent, as scripts/qualify_identity.py arranges them. `owner` is workspace A's
 * owner, or the install's owner on the persistent install; `ownerB` owns workspace B; `member` is
 * a member of workspace A who owns another workspace; `reader` is a member of workspace A only.
 * The rest each own a workspace arranged for one screen.
 */
export const users = {
  get owner(): Credentials {
    return role("AUTOBOTS_TEST_OWNER");
  },
  get ownerB(): Credentials {
    return role("AUTOBOTS_TEST_OWNER_B");
  },
  get member(): Credentials {
    return role("AUTOBOTS_TEST_MEMBER");
  },
  get reader(): Credentials {
    return role("AUTOBOTS_TEST_READER");
  },
  get ops(): Credentials {
    return role("AUTOBOTS_TEST_OPS");
  },
  get runs(): Credentials {
    return role("AUTOBOTS_TEST_RUNS");
  },
  get experts(): Credentials {
    return role("AUTOBOTS_TEST_EXPERTS");
  },
  get models(): Credentials {
    return role("AUTOBOTS_TEST_MODELS");
  },
  get composer(): Credentials {
    return role("AUTOBOTS_TEST_COMPOSER");
  },
  get home(): Credentials {
    return role("AUTOBOTS_TEST_HOME");
  },
  get flows(): Credentials {
    return role("AUTOBOTS_TEST_FLOWS");
  },
  get multi(): Credentials {
    return role("AUTOBOTS_TEST_MULTI");
  },
  get files(): Credentials {
    return role("AUTOBOTS_TEST_FILES");
  },
  get noKey(): Credentials {
    return role("AUTOBOTS_TEST_NO_KEY");
  },
};

/** Fills the sign-in form and submits it, asserting nothing about the outcome. */
export async function submitSignIn(
  page: Page,
  { email, password }: Credentials,
): Promise<void> {
  await page.goto("/sign-in");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

/** Signs in through the form, and waits until the page says so. */
export async function signIn(page: Page, user: Credentials): Promise<void> {
  await submitSignIn(page, user);
  await expect(page.getByText(/Signed in, with access to/)).toBeVisible();
}

/**
 * Gives a page's context a session cookie minted by scripts/qualify_web.py, for the web suites,
 * whose stack has no sign-in service.
 */
export async function addSessionCookie(
  page: Page,
  token: string,
  url: string = webOrigin(),
): Promise<void> {
  await page
    .context()
    .addCookies([{ name: "autobots.session", value: token, url }]);
}
