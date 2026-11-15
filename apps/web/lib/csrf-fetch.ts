/**
 * A same-origin write with the double-submit token. Runs in the browser.
 *
 * R-19: the token is fetched once and cached, and a write refused for its token fetches a fresh one
 * and is sent once more. The request guard refuses before anything is forwarded, so that resend
 * can't repeat a write.
 */
import { parseCsrfToken, type CsrfToken } from "./api/bff-bodies.ts";

const REFUSED_TOKEN = new Set(["invalid_csrf", "missing_csrf"]);
let cached: Promise<CsrfToken> | null = null;

function csrfToken(fresh: boolean): Promise<CsrfToken> {
  if (fresh || cached === null) {
    cached = fetch("/api/csrf", { cache: "no-store" })
      .then((reply) => reply.json())
      .then(parseCsrfToken);
    // A failed fetch isn't kept, so the next write asks again.
    cached.catch(() => {
      cached = null;
    });
  }
  return cached;
}

async function send(
  path: string,
  init: RequestInit,
  fresh: boolean,
): Promise<Response> {
  const { header, token } = await csrfToken(fresh);
  return fetch(path, {
    ...init,
    headers: { ...init.headers, [header]: token },
  });
}

export async function csrfFetch(
  path: string,
  init: RequestInit,
): Promise<Response> {
  const reply = await send(path, init, false);
  if (reply.status !== 403) return reply;
  const body: unknown = await reply
    .clone()
    .json()
    .catch(() => null);
  const code =
    typeof body === "object" && body !== null && "code" in body
      ? body.code
      : null;
  return typeof code === "string" && REFUSED_TOKEN.has(code)
    ? send(path, init, true)
    : reply;
}

/** For tests: forget the cached token. */
export function forgetCsrfToken(): void {
  cached = null;
}
