/**
 * Reads and writes through the BFF, checked against the generated contract (TWEB-04, XTYP-18). A
 * reply's status is asserted before its body is parsed, so a failed arrangement names its route
 * and reply instead of surfacing later as `undefined`.
 */
import { parseErrorResponse, type ErrorResponse } from "@autobots/api-client";
import {
  expect,
  type APIRequestContext,
  type APIResponse,
  type Page,
} from "@playwright/test";

export type Parse<T> = (value: unknown) => T;

/** A reply from a request context, or a page's own response, as a refusal is checked on either. */
export type Reply = Pick<APIResponse, "status" | "url" | "text">;

/** The BFF's double-submit token (app/api/csrf/route.ts). It isn't in the service's contract. */
export interface CsrfToken {
  header: string;
  token: string;
}

function parseCsrfToken(value: unknown): CsrfToken {
  if (typeof value === "object" && value !== null) {
    const { header, token } = value as Record<string, unknown>;
    if (typeof header === "string" && typeof token === "string") {
      return { header, token };
    }
  }
  throw new Error(`/api/csrf: not a CSRF token: ${JSON.stringify(value)}`);
}

async function bodyOf(reply: Reply): Promise<unknown> {
  const text = await reply.text();
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(`${reply.url()}: not JSON: ${text.slice(0, 300)}`);
  }
}

/** A CSRF token from `url`, through any request context, such as a test's own `request`. */
export async function readCsrfToken(
  request: APIRequestContext,
  url = "/api/csrf",
): Promise<CsrfToken> {
  const reply = await request.get(url);
  expect(reply.status(), `GET ${url}`).toBe(200);
  return parseCsrfToken(await bodyOf(reply));
}

/** The session's CSRF token, through the page's own context. */
export function csrfToken(page: Page): Promise<CsrfToken> {
  return readCsrfToken(page.request);
}

/** What a write through the BFF needs, with no idempotency key: the CSRF token, origin and JSON. */
export async function csrfHeaders(page: Page): Promise<Record<string, string>> {
  const { header, token } = await csrfToken(page);
  return {
    [header]: token,
    Origin: new URL(page.url()).origin,
    "Content-Type": "application/json",
  };
}

/**
 * csrfHeaders with an Idempotency-Key: a fresh one unless the test names one, as a replay or a
 * conflict needs.
 */
export async function writeHeaders(
  page: Page,
  key: string = crypto.randomUUID(),
): Promise<Record<string, string>> {
  return { ...(await csrfHeaders(page)), "Idempotency-Key": key };
}

/** Reads `path` through the page's context, asserts the status, then parses the body. */
export async function getJson<T>(
  page: Page,
  {
    path,
    parse,
    status = 200,
    headers,
  }: {
    path: string;
    parse: Parse<T>;
    status?: number;
    headers?: Record<string, string>;
  },
): Promise<T> {
  const reply = await page.request.get(path, headers ? { headers } : {});
  expect(reply.status(), `GET ${path}: ${await reply.text()}`).toBe(status);
  return parse(await bodyOf(reply));
}

/**
 * Writes `data` to `path` with the CSRF headers, asserts the status, then parses the body. `key`
 * is the Idempotency-Key, a fresh one when left out, and none when null.
 */
export async function send<T>(
  page: Page,
  {
    method = "POST",
    path,
    data,
    key,
    status,
    parse,
    headers,
  }: {
    method?: "POST" | "PUT" | "DELETE";
    path: string;
    data?: unknown;
    key?: string | null;
    status: number;
    parse: Parse<T>;
    headers?: Record<string, string>;
  },
): Promise<T> {
  const written =
    key === null ? await csrfHeaders(page) : await writeHeaders(page, key);
  const reply = await page.request.fetch(path, {
    method,
    headers: { ...written, ...headers },
    ...(data === undefined ? {} : { data }),
  });
  expect(reply.status(), `${method} ${path}: ${await reply.text()}`).toBe(
    status,
  );
  return parse(await bodyOf(reply));
}

/** Asserts a refusal's status, parses its error body, and checks its code when one is given. */
export async function expectRefusal(
  reply: Reply,
  { status, code }: { status: number; code?: string },
): Promise<ErrorResponse> {
  expect(reply.status(), `${reply.url()}: ${await reply.text()}`).toBe(status);
  const refusal = parseErrorResponse(await bodyOf(reply));
  if (code !== undefined) expect(refusal.code, reply.url()).toBe(code);
  return refusal;
}
