/**
 * What a caught failure means for the person, and the one log record it leaves (WSHL-02, XERR-05).
 * Pure, so `node --test` runs the classification; `server-log.ts` writes the record on the server.
 */
import { ContractError, HttpFailure } from "@autobots/api-client/runtime";
import { isAuthError, isAuthRetryableFetchError } from "@supabase/supabase-js";

import { ConfigurationError } from "./server-env.ts";

/** A status and the service's `{code, message}` envelope. No cause reaches the browser. */
export interface Refusal {
  readonly status: number;
  readonly code: string;
  readonly message: string;
}

export const NOT_SIGNED_IN: Refusal = {
  status: 401,
  code: "not_signed_in",
  message: "Sign in first.",
};
export const SIGN_IN_FAILED: Refusal = {
  status: 401,
  code: "sign_in_failed",
  message: "That email and password did not work.",
};
export const TOO_LARGE: Refusal = {
  status: 413,
  code: "request_too_large",
  message: "This request is too large.",
};
export const API_UNAVAILABLE: Refusal = {
  status: 503,
  code: "service_unavailable",
  message: "The local API is unavailable.",
};
export const AUTH_UNAVAILABLE: Refusal = {
  status: 503,
  code: "auth_unavailable",
  message: "The sign-in service is unavailable.",
};
export const MISCONFIGURED: Refusal = {
  status: 503,
  code: "server_misconfigured",
  message: "The web server is missing part of its configuration.",
};
// The request may still have reached the API, so a write's outcome is unknown (lib/submit.ts).
export const API_TIMEOUT: Refusal = {
  status: 504,
  code: "upstream_timeout",
  message: "The local API did not answer in time.",
};

/** A same-origin or CSRF refusal from `guardRequest`, which names its reason in the code. */
export function guardRefusal(code: string): Refusal {
  return { status: 403, code, message: "This request was refused." };
}

/** `AbortSignal.timeout` rejects with a `TimeoutError`, which fetch may wrap as the cause. */
export function timedOut(error: unknown): boolean {
  let current = error;
  for (let depth = 0; depth < 4; depth += 1) {
    if (typeof current !== "object" || current === null) return false;
    if ("name" in current && current.name === "TimeoutError") return true;
    current = "cause" in current ? current.cause : undefined;
  }
  return false;
}

/**
 * The answer to a failure a route caught. `service` names what the route depends on, so an
 * unclassified failure in the session route reads as Auth being unavailable, not the API.
 */
export function failureRefusal(
  error: unknown,
  service: "api" | "auth" = "api",
): Refusal {
  if (error instanceof ConfigurationError) return MISCONFIGURED;
  if (service === "auth" || isAuthRetryableFetchError(error)) {
    return AUTH_UNAVAILABLE;
  }
  return timedOut(error) ? API_TIMEOUT : API_UNAVAILABLE;
}

// Auth's answers about the email and password themselves. A 401 or 403 comes from the gateway in
// front of Auth, such as a wrong anon key, and is no fault of the person's.
const CREDENTIAL_STATUSES: ReadonlySet<number> = new Set([400, 422]);

/**
 * Sign-in's answer to an Auth error. Only Auth's 400 and 422 refusals are about the credentials, and
 * they never say which field failed. A 401 or 403 from the gateway, a rate limit, a 5xx or no reply
 * is an outage (WSHL-07).
 */
export function signInRefusal(error: unknown): Refusal {
  const status = isAuthError(error) ? error.status : undefined;
  return status !== undefined && CREDENTIAL_STATUSES.has(status)
    ? SIGN_IN_FAILED
    : AUTH_UNAVAILABLE;
}

/** A member read is signed out only when the API answers 401; anything else is unavailable. */
export function readFailure(error: unknown): "signed_out" | "unavailable" {
  return error instanceof HttpFailure && error.status === 401
    ? "signed_out"
    : "unavailable";
}

export interface FailureRecord {
  at: string;
  level: "error";
  logger: "web";
  event: "web.failure";
  operation: string;
  error: string;
  path?: string;
  status?: number;
  timeout: boolean;
  /** For a `ConfigurationError`: the names of the missing variables, never their values (WSHL-20). */
  variables?: string[];
}

const CLASS_NAME = /^[A-Za-z][A-Za-z0-9_]{0,63}$/;
const PATH_LIMIT = 200;

function className(error: unknown): string {
  if (typeof error !== "object" || error === null) return typeof error;
  const name = "name" in error ? error.name : undefined;
  return typeof name === "string" && CLASS_NAME.test(name) ? name : "Error";
}

function statusOf(error: unknown): number | undefined {
  if (error instanceof HttpFailure) return error.status;
  return isAuthError(error) ? error.status : undefined;
}

/**
 * The operation, the error class, a `ContractError`'s schema path, the HTTP or Auth status, whether
 * a timeout fired and, for missing configuration, the variables' names. Never a message, body,
 * header, token, query string or value, which can carry a credential or a person's content
 * (PRD-Development-Harness DH-06). A schema path can include a key of a map-typed field.
 */
export function failureRecord(
  operation: string,
  error: unknown,
  at: Date,
): FailureRecord {
  const status = statusOf(error);
  return {
    at: at.toISOString(),
    level: "error",
    logger: "web",
    event: "web.failure",
    operation,
    error: className(error),
    ...(error instanceof ContractError
      ? { path: error.path.slice(0, PATH_LIMIT) }
      : {}),
    ...(status === undefined ? {} : { status }),
    timeout: timedOut(error),
    ...(error instanceof ConfigurationError
      ? { variables: [...error.variables] }
      : {}),
  };
}
