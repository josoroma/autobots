import "server-only";

export interface ServerConfig {
  apiUrl: string;
  internalToken: string;
  allowedOrigin: string;
  supabaseUrl: string;
  supabaseAnonKey: string;
}

/** Read per call, so a value is never compiled into a build. `server-only` keeps it out of client bundles. */
export function serverConfig(): ServerConfig {
  return {
    apiUrl: process.env.AUTOBOTS_API_URL ?? "http://127.0.0.1:8001",
    internalToken: process.env.AUTOBOTS_INTERNAL_TOKEN ?? "",
    allowedOrigin:
      process.env.AUTOBOTS_ALLOWED_ORIGIN ?? "http://127.0.0.1:3000",
    supabaseUrl: process.env.AUTOBOTS_SUPABASE_URL ?? "http://127.0.0.1:54321",
    supabaseAnonKey: process.env.AUTOBOTS_SUPABASE_ANON_KEY ?? "",
  };
}
