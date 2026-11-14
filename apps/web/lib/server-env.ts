/**
 * The web server's settings, read from its environment and checked before use, so a missing secret
 * or a malformed address fails where it is read rather than as a signed-out page (WSHL-20). Pure, so
 * `node --test` runs the checks; `server-config.ts` passes `process.env` on the server.
 */
export interface ServerConfig {
  apiUrl: string;
  internalToken: string;
  allowedOrigin: string;
  supabaseUrl: string;
  supabaseAnonKey: string;
}

/** Names the variables that are missing or malformed, and never their values. */
export class ConfigurationError extends Error {
  readonly variables: readonly string[];

  constructor(variables: readonly string[]) {
    super(`Set ${variables.join(", ")} for the web server.`);
    this.name = "ConfigurationError";
    this.variables = variables;
  }
}

function isHttpUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

/** The request guard compares the browser's Origin header as text, so no path or trailing slash. */
function isHttpOrigin(value: string): boolean {
  return isHttpUrl(value) && new URL(value).origin === value;
}

/**
 * The local addresses default to this Mac's ports. The internal token and the anon key have no
 * default: the API refuses an empty token and the Auth client an empty key (WSHL-20).
 */
export function configFrom(
  env: Readonly<Record<string, string | undefined>>,
): ServerConfig {
  const config: ServerConfig = {
    apiUrl: env.AUTOBOTS_API_URL ?? "http://127.0.0.1:8001",
    internalToken: env.AUTOBOTS_INTERNAL_TOKEN ?? "",
    allowedOrigin: env.AUTOBOTS_ALLOWED_ORIGIN ?? "http://127.0.0.1:3000",
    supabaseUrl: env.AUTOBOTS_SUPABASE_URL ?? "http://127.0.0.1:54321",
    supabaseAnonKey: env.AUTOBOTS_SUPABASE_ANON_KEY ?? "",
  };
  const invalid = [
    isHttpUrl(config.apiUrl) ? null : "AUTOBOTS_API_URL",
    config.internalToken === "" ? "AUTOBOTS_INTERNAL_TOKEN" : null,
    isHttpOrigin(config.allowedOrigin) ? null : "AUTOBOTS_ALLOWED_ORIGIN",
    isHttpUrl(config.supabaseUrl) ? null : "AUTOBOTS_SUPABASE_URL",
    config.supabaseAnonKey === "" ? "AUTOBOTS_SUPABASE_ANON_KEY" : null,
  ].filter((name) => name !== null);
  if (invalid.length > 0) {
    throw new ConfigurationError(invalid);
  }
  return config;
}
