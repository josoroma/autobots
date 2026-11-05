import "server-only";

export interface ServerConfig {
  apiUrl: string;
  internalToken: string;
  allowedOrigin: string;
}

/** Read per call, so a value is never compiled into a build. `server-only` keeps it out of client bundles. */
export function serverConfig(): ServerConfig {
  return {
    apiUrl: process.env.AUTOBOTS_API_URL ?? "http://127.0.0.1:8001",
    internalToken: process.env.AUTOBOTS_INTERNAL_TOKEN ?? "",
    allowedOrigin:
      process.env.AUTOBOTS_ALLOWED_ORIGIN ?? "http://127.0.0.1:3000",
  };
}
