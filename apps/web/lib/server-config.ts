import "server-only";

import { configFrom, type ServerConfig } from "@/lib/server-env";

export type { ServerConfig };

/**
 * Read per call, so a value is never compiled into a build. `server-only` keeps it out of client
 * bundles. Throws `ConfigurationError`, naming the variables only, when a secret is missing or an
 * address is malformed (WSHL-20).
 */
export function serverConfig(): ServerConfig {
  return configFrom(process.env);
}
