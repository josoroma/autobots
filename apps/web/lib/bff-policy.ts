/**
 * What the BFF decides without any I/O: body limits, which headers cross in each direction, the
 * cookie policy, reading a JSON body and the route a log line names (WSHL-05, WSHL-15). Pure, so
 * `node --test` covers it; `bff.ts` applies it on the server.
 */

// The chosen workspace travels to the API in this header (Decision 0023 E3).
export const WORKSPACE_HEADER = "x-autobots-workspace";
export const MAX_BODY_BYTES = 64 * 1024;
// A goal may carry up to five attached text files of 1 MiB each (PRD-Tool-Catalog FI-01), which
// JSON escaping can grow. Only run creation gets this; every other route keeps the small limit.
export const RUN_BODY_BYTES = 12 * 1024 * 1024;

// The internal token, the bearer and cookies are never copied from the browser.
const REQUEST_HEADERS: readonly string[] = [
  "content-type",
  WORKSPACE_HEADER,
  "idempotency-key",
];
const RESPONSE_HEADERS: readonly string[] = [
  "content-disposition",
  "x-content-type-options",
];

export function bodyLimit(method: string, apiPath: string): number {
  return method === "POST" && apiPath.split("?")[0] === "/v1/runs"
    ? RUN_BODY_BYTES
    : MAX_BODY_BYTES;
}

/** The headers every API call carries: the internal token, then the session and workspace if any. */
export function apiHeaders(
  internalToken: string,
  accessToken: string | null,
  workspace: string | null,
): Record<string, string> {
  return {
    "X-Autobots-Internal": internalToken,
    ...(accessToken === null ? {} : { Authorization: `Bearer ${accessToken}` }),
    ...(workspace === null ? {} : { [WORKSPACE_HEADER]: workspace }),
  };
}

/**
 * The API headers plus the allowlisted request headers. A workspace header the browser sends
 * replaces the chosen one, and the API checks membership for it the same way (Decision 0023 E3).
 */
export function forwardedHeaders(
  request: Headers,
  base: Record<string, string>,
): Headers {
  const headers = new Headers(base);
  for (const name of REQUEST_HEADERS) {
    const value = request.get(name);
    if (value !== null) {
      headers.set(name, value);
    }
  }
  return headers;
}

/** A relayed reply is never cached, and keeps only its type and allowlisted headers. */
export function relayHeaders(reply: Headers): Headers {
  const headers = new Headers({
    "Content-Type": reply.get("content-type") ?? "application/json",
    "Cache-Control": "no-store",
  });
  for (const name of RESPONSE_HEADERS) {
    const value = reply.get(name);
    if (value !== null) {
      headers.set(name, value);
    }
  }
  return headers;
}

export interface CookiePolicy {
  httpOnly: boolean;
  sameSite: "strict";
  path: "/";
  secure: boolean;
}

/** One policy for the app's cookies: strict, site-wide, and Secure when the origin is https. */
export function cookieOptions(
  allowedOrigin: string,
  httpOnly: boolean,
): CookiePolicy {
  return {
    httpOnly,
    sameSite: "strict",
    path: "/",
    secure: new URL(allowedOrigin).protocol === "https:",
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** A JSON object body, or null for anything else, including a body that isn't JSON. */
export async function readJsonObject(
  request: Request,
): Promise<Record<string, unknown> | null> {
  const body: unknown = await request.json().catch(() => null);
  return isRecord(body) ? body : null;
}

const LITERAL = /^[a-z][a-z0-9-]{0,63}$/;
const IDENTIFIER =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * The route a log line names. The query is dropped, and any segment that isn't a lowercase path
 * word, such as a run's identifier or a variable's name, becomes `{param}` (XERR-05).
 */
export function routeTemplate(apiPath: string): string {
  const path = apiPath.split(/[?#]/, 1)[0] ?? "";
  return path
    .split("/")
    .map((segment) =>
      segment === "" || (LITERAL.test(segment) && !IDENTIFIER.test(segment))
        ? segment
        : "{param}",
    )
    .join("/");
}
