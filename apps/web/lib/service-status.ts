import "server-only";

import { getHealth } from "@autobots/api-client";

import { serverConfig } from "@/lib/server-config";

export type ServiceStatus = "available" | "unavailable";

/** An unreachable or invalid API is a visible state, and its details stay on the server. */
export async function fetchServiceStatus(): Promise<ServiceStatus> {
  const config = serverConfig();
  try {
    await getHealth({
      baseUrl: config.apiUrl,
      fetch: (input, init) =>
        fetch(input, {
          ...init,
          cache: "no-store",
          signal: AbortSignal.timeout(3_000),
        }),
      headers: { "X-Autobots-Internal": config.internalToken },
    });
    return "available";
  } catch {
    return "unavailable";
  }
}
