import { NextResponse, type NextRequest } from "next/server";

import { CSRF_COOKIE, CSRF_HEADER, guardRequest } from "@/lib/request-guard";
import { serverConfig } from "@/lib/server-config";
import { fetchSession } from "@/lib/service-status";
import { isWorkspaceId, WORKSPACE_COOKIE } from "@/lib/workspace-choice";

function refused(status: number, code: string, message: string): NextResponse {
  return NextResponse.json(
    { code, message },
    { status, headers: { "Cache-Control": "no-store" } },
  );
}

/**
 * Decision 0023 E3: choose the workspace. Same origin and CSRF-checked, signed in, and only a
 * workspace the verified session belongs to. The API still checks membership on every request.
 */
export async function POST(request: NextRequest): Promise<NextResponse> {
  const config = serverConfig();
  const refusal = guardRequest(
    {
      method: request.method,
      host: request.headers.get("host"),
      origin: request.headers.get("origin"),
      fetchSite: request.headers.get("sec-fetch-site"),
      csrfHeader: request.headers.get(CSRF_HEADER),
      csrfCookie: request.cookies.get(CSRF_COOKIE)?.value ?? null,
    },
    { allowedOrigin: config.allowedOrigin },
  );
  if (refusal !== null) {
    return refused(403, refusal, "This request was refused.");
  }
  const body: unknown = await request.json().catch(() => null);
  const chosen = (body as { workspace_id?: unknown } | null)?.workspace_id;
  if (!isWorkspaceId(chosen)) {
    return refused(422, "invalid_workspace", "Choose one of your workspaces.");
  }
  const session = await fetchSession();
  if (session === null) {
    return refused(401, "not_signed_in", "Sign in first.");
  }
  if (!session.workspace_ids.includes(chosen)) {
    return refused(403, "forbidden", "This workspace is not available.");
  }
  const reply = NextResponse.json(
    { workspace_id: chosen },
    { headers: { "Cache-Control": "no-store" } },
  );
  reply.cookies.set(WORKSPACE_COOKIE, chosen, {
    httpOnly: true,
    sameSite: "strict",
    path: "/",
    secure: new URL(config.allowedOrigin).protocol === "https:",
  });
  return reply;
}
