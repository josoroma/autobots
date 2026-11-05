import "server-only";

import {
  getHealth,
  getSession,
  type SessionSummary,
} from "@autobots/api-client";

import { serverConfig } from "@/lib/server-config";
import { accessToken } from "@/lib/session";

export type ServiceStatus = "available" | "unavailable";

function client(headers: Record<string, string>) {
  const config = serverConfig();
  return {
    baseUrl: config.apiUrl,
    fetch: ((input, init) =>
      fetch(input, {
        ...init,
        cache: "no-store",
        signal: AbortSignal.timeout(3_000),
      })) as typeof fetch,
    headers: { "X-Autobots-Internal": config.internalToken, ...headers },
  };
}

/** An unreachable or invalid API is a visible state, and its details stay on the server. */
export async function fetchServiceStatus(): Promise<ServiceStatus> {
  try {
    await getHealth(client({}));
    return "available";
  } catch {
    return "unavailable";
  }
}

/** The verified session as the API sees it, or null when signed out or refused. */
export async function fetchSession(): Promise<SessionSummary | null> {
  try {
    const token = await accessToken();
    return token === null
      ? null
      : await getSession(client({ Authorization: `Bearer ${token}` }));
  } catch {
    return null;
  }
}
