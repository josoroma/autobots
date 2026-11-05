// Same-origin checks for the BFF. Pure, so they can be tested without a server.

export const CSRF_COOKIE = "autobots.csrf";
export const CSRF_HEADER = "x-autobots-csrf";
export const SESSION_COOKIE = "autobots.session";

export interface GuardInput {
  method: string;
  host: string | null;
  origin: string | null;
  fetchSite: string | null;
  csrfHeader: string | null;
  csrfCookie: string | null;
}

export interface GuardPolicy {
  allowedOrigin: string;
}

const SAFE_METHODS = new Set(["GET", "HEAD"]);

function constantTimeEqual(left: string, right: string): boolean {
  if (left.length !== right.length) {
    return false;
  }
  let difference = 0;
  for (let index = 0; index < left.length; index += 1) {
    difference |= left.charCodeAt(index) ^ right.charCodeAt(index);
  }
  return difference === 0;
}

/** The reason to refuse, or null. Loopback does not authorize anything by itself. */
export function guardRequest(
  input: GuardInput,
  policy: GuardPolicy,
): string | null {
  if (input.host !== new URL(policy.allowedOrigin).host) {
    return "forbidden_host";
  }
  if (input.origin !== null && input.origin !== policy.allowedOrigin) {
    return "forbidden_origin";
  }
  if (
    input.fetchSite !== null &&
    input.fetchSite !== "same-origin" &&
    input.fetchSite !== "none"
  ) {
    return "forbidden_origin";
  }
  if (SAFE_METHODS.has(input.method)) {
    return null;
  }
  if (input.origin === null) {
    return "forbidden_origin";
  }
  if (
    input.csrfHeader === null ||
    input.csrfCookie === null ||
    input.csrfCookie === ""
  ) {
    return "missing_csrf";
  }
  return constantTimeEqual(input.csrfHeader, input.csrfCookie)
    ? null
    : "invalid_csrf";
}
