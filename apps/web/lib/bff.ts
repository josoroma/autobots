import "server-only";

import { NextResponse, type NextRequest } from "next/server";

import { CSRF_COOKIE, CSRF_HEADER, guardRequest } from "@/lib/request-guard";
import { serverConfig } from "@/lib/server-config";
import { accessToken } from "@/lib/session";

const MAX_BODY_BYTES = 64 * 1024;

function safeError(
  status: number,
  code: string,
  message: string,
): NextResponse {
  return NextResponse.json(
    { code, message },
    { status, headers: { "Cache-Control": "no-store" } },
  );
}

/**
 * The browser only ever talks to these same-origin routes. The internal token is added here, on the
 * server, and anything the client sent under that name is dropped. Bodies are forwarded unread and
 * never logged, so a draft key cannot reach a response or a log from this layer.
 */
export async function forward(
  request: NextRequest,
  apiPath: string,
): Promise<NextResponse> {
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
    return safeError(403, refusal, "This request was refused.");
  }
  const session = await accessToken();
  if (session === null) {
    return safeError(401, "not_signed_in", "Sign in first.");
  }
  const headers = new Headers({
    Authorization: `Bearer ${session}`,
    "X-Autobots-Internal": config.internalToken,
  });
  for (const name of ["content-type", "x-autobots-workspace"]) {
    const value = request.headers.get(name);
    if (value !== null) {
      headers.set(name, value);
    }
  }
  try {
    const body =
      request.method === "GET" || request.method === "HEAD"
        ? null
        : await request.arrayBuffer();
    if (body !== null && body.byteLength > MAX_BODY_BYTES) {
      return safeError(413, "request_too_large", "This request is too large.");
    }
    const reply = await fetch(new URL(apiPath, config.apiUrl), {
      method: request.method,
      headers,
      redirect: "error",
      signal: AbortSignal.timeout(30_000),
      ...(body === null ? {} : { body }),
    });
    return new NextResponse(await reply.arrayBuffer(), {
      status: reply.status,
      headers: {
        "Content-Type": reply.headers.get("content-type") ?? "application/json",
        "Cache-Control": "no-store",
      },
    });
  } catch {
    return safeError(
      503,
      "service_unavailable",
      "The local API is unavailable.",
    );
  }
}
