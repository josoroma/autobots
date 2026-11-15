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

function client(headers: Record<string, string>): ClientOptions {
  const timed: typeof fetch = (input, init) =>
    fetch(input, {
      ...init,
      cache: "no-store",
      signal: AbortSignal.timeout(3_000),
    });
  return { baseUrl: serverConfig().apiUrl, fetch: timed, headers };
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
    const token = await accessToken();
    if (token === null) return SIGNED_OUT;
    // A member read carries the chosen workspace when there is one (Decision 0023 E3).
    const workspace = withWorkspace ? await chosenWorkspace() : null;
    const headers = apiHeaders(serverConfig().internalToken, token, workspace);
    return { kind: "ok", value: await call(client(headers)) };
  } catch (error) {
    unstable_rethrow(error);
    if (readFailure(error) === "signed_out") return SIGNED_OUT;
    logFailure(operation, error);
    return UNAVAILABLE;
  }
}

/** An unreachable or invalid API is a visible state, and its details stay in the server's log. */
export async function fetchServiceStatus(): Promise<ServiceStatus> {
  try {
    await getHealth(
      client(apiHeaders(serverConfig().internalToken, null, null)),
    );
    return "available";
  } catch (error) {
    unstable_rethrow(error);
    logFailure("health.read", error);
    return "unavailable";
  }
}

/** The verified session as the API sees it. */
export function fetchSession(): Promise<MemberRead<SessionSummary>> {
  return memberRead("session.read", getSession, false);
}

/** PRD-Studio SH-04: readiness any member may read. */
export function fetchReadiness(): Promise<MemberRead<MemberReadiness>> {
  return memberRead("readiness.read", getReadiness, true);
}

/** PRD-Studio SH-03: the number of pending approvals, from a count rather than a listed page. */
export function fetchPendingApprovals(): Promise<MemberRead<number>> {
  return memberRead(
    "approvals.count",
    async (options) => (await countPendingApprovals(options)).pending,
    true,
  );
}
