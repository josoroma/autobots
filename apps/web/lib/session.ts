import "server-only";

import { createServerClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";
import { cookies } from "next/headers";

import { SESSION_COOKIE } from "@/lib/request-guard";
import { serverConfig } from "@/lib/server-config";

/** The Supabase client stays on the server. The browser holds only an HttpOnly session cookie. */
export async function sessionClient(): Promise<SupabaseClient> {
  const store = await cookies();
  const config = serverConfig();
  return createServerClient(config.supabaseUrl, config.supabaseAnonKey, {
    cookieOptions: {
      name: SESSION_COOKIE,
      httpOnly: true,
      sameSite: "strict",
      secure: false,
      path: "/",
    },
    cookies: {
      getAll: () => store.getAll(),
      setAll: (values) => {
        try {
          values.forEach(({ name, value, options }) =>
            store.set(name, value, options),
          );
        } catch {
          // A Server Component cannot set cookies. A route handler refreshes them instead.
        }
      },
    },
  });
}

/** The token for the Python API, which verifies it itself. Nothing here trusts its contents. */
export async function accessToken(): Promise<string | null> {
  const client = await sessionClient();
  const { data } = await client.auth.getSession();
  return data.session?.access_token ?? null;
}
