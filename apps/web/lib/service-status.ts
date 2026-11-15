import "server-only";

import {
  countPendingApprovals,
  getHealth,
  getReadiness,
  getSession,
  type MemberReadiness,
  type SessionSummary,
} from "@autobots/api-client";
import type { ClientOptions } from "@autobots/api-client/runtime";
import { unstable_rethrow } from "next/navigation";
import { cache } from "react";

import { apiHeaders } from "@/lib/bff-policy";
import { readFailure } from "@/lib/failure";
import { serverConfig } from "@/lib/server-config";
import { logFailure } from "@/lib/server-log";
import { accessToken } from "@/lib/session";
import { chosenWorkspace } from "@/lib/workspace-choice";

export type ServiceStatus = "available" | "unavailable";

/**
 * A server read for the signed-in person (WSHL-02). Signed out means there is no session or the API
 * answered 401. Anything else, such as a stopped API, a timeout, missing configuration or a reply
 * that has drifted from its contract, is unavailable, and its cause is logged on the server.
 */
export type MemberRead<T> =
  { kind: "ok"; value: T } | { kind: "signed_out" } | { kind: "unavailable" };

const SIGNED_OUT: { kind: "signed_out" } = { kind: "signed_out" };
const UNAVAILABLE: { kind: "unavailable" } = { kind: "unavailable" };

/** The value of a read that succeeded, or null, for views that show nothing otherwise. */
export function readValue<T>(read: MemberRead<T>): T | null {
  return read.kind === "ok" ? read.value : null;
}

// The shell's reads give up after 3 s, so a stopped API never holds the frame back (WSHL-02).
const SHELL_TIMEOUT_MS = 3_000;

/**
 * Options for the server's own reads. Never from a cache: each read is this request's, for this
 * person and workspace (PRD-Development-Harness DH-06).
 */
function client(
  headers: Record<string, string>,
  timeoutMs: number,
): ClientOptions {
  const timed: typeof fetch = (input, init) =>
    fetch(input, {
      ...init,
      cache: "no-store",
      signal: AbortSignal.timeout(timeoutMs),
    });
  return { baseUrl: serverConfig().apiUrl, fetch: timed, headers };
}

/**
 * Options for one person's read, as the BFF sends it (lib/bff.ts): the internal token, the
 * session's token and, when `withWorkspace`, the chosen workspace, which the API checks against
 * membership (Decision 0023 E3). Null when no one is signed in. Throws when Auth can't be reached or
 * the server's configuration is missing, so neither reads as a sign-out (WSHL-02).
 */
export async function memberClient(
  withWorkspace: boolean,
  timeoutMs: number,
): Promise<ClientOptions | null> {
  const token = await accessToken();
  if (token === null) return null;
  const workspace = withWorkspace ? await chosenWorkspace() : null;
  return client(
    apiHeaders(serverConfig().internalToken, token, workspace),
    timeoutMs,
  );
}

/**
 * Next's own control flow, such as the bail-out a request-time API throws while a page is being
 * prerendered, is rethrown rather than read or logged as a failure.
 */
async function memberRead<T>(
  operation: string,
  call: (options: ClientOptions) => Promise<T>,
  withWorkspace: boolean,
): Promise<MemberRead<T>> {
  try {
    const options = await memberClient(withWorkspace, SHELL_TIMEOUT_MS);
    if (options === null) return SIGNED_OUT;
    return { kind: "ok", value: await call(options) };
  } catch (error) {
    unstable_rethrow(error);
    if (readFailure(error) === "signed_out") return SIGNED_OUT;
    logFailure(operation, error);
    return UNAVAILABLE;
  }
}

// Each read below is wrapped in React's `cache()`, which keeps a result for one server request
// only, so the shell and the page share one read per render and nothing outlives the request
// (WSHL-14, PRD-Development-Harness DH-06).

/** An unreachable or invalid API is a visible state, and its details stay in the server's log. */
export const fetchServiceStatus = cache(async (): Promise<ServiceStatus> => {
  try {
    await getHealth(
      client(
        apiHeaders(serverConfig().internalToken, null, null),
        SHELL_TIMEOUT_MS,
      ),
    );
    return "available";
  } catch (error) {
    unstable_rethrow(error);
    logFailure("health.read", error);
    return "unavailable";
  }
});

/** The verified session as the API sees it. */
export const fetchSession = cache((): Promise<MemberRead<SessionSummary>> =>
  memberRead("session.read", getSession, false),
);

/** PRD-Studio SH-04: readiness any member may read. */
export const fetchReadiness = cache((): Promise<MemberRead<MemberReadiness>> =>
  memberRead("readiness.read", getReadiness, true),
);

/** PRD-Studio SH-03: the number of pending approvals, from a count rather than a listed page. */
export const fetchPendingApprovals = cache((): Promise<MemberRead<number>> =>
  memberRead(
    "approvals.count",
    async (options) => (await countPendingApprovals(options)).pending,
    true,
  ),
);
