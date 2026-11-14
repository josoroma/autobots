/**
 * A same-origin write with the double-submit token. Runs in the browser.
 *
 * R-19: the token is fetched once and cached, and a write refused for its token fetches a fresh one
 * and is sent once more. The request guard refuses before anything is forwarded, so that resend
 * can't repeat a write.
 */
interface Token {
  header: string;
  token: string;
}

const REFUSED_TOKEN = new Set(["invalid_csrf", "missing_csrf"]);
let cached: Promise<Token> | null = null;

function csrfToken(fresh: boolean): Promise<Token> {
  if (fresh || cached === null) {
    cached = fetch("/api/csrf", { cache: "no-store" })
      .then((reply) => reply.json())
      .then((body: unknown) => {
        if (
          typeof body === "object" &&
          body !== null &&
          "header" in body &&
          "token" in body &&
          typeof body.header === "string" &&
          typeof body.token === "string"
        ) {
          return { header: body.header, token: body.token };
        }
        throw new Error("the CSRF token reply is malformed");
      });
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
