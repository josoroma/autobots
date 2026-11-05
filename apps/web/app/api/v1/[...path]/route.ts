import { NextResponse, type NextRequest } from "next/server";

import { guardRequest } from "@/lib/request-guard";
import { serverConfig } from "@/lib/server-config";
import { accessToken } from "@/lib/session";

type Context = { params: Promise<{ path: string[] }> };

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

// The browser only ever talks to this same-origin route. The internal token is added here, on the
// server, and anything the client sent under that name is dropped.
async function forward(
  request: NextRequest,
  context: Context,
): Promise<NextResponse> {
  const config = serverConfig();
  const refusal = guardRequest(
    {
      method: request.method,
      host: request.headers.get("host"),
      origin: request.headers.get("origin"),
      fetchSite: request.headers.get("sec-fetch-site"),
      csrfHeader: request.headers.get("x-autobots-csrf"),
      csrfCookie: request.cookies.get("autobots.csrf")?.value ?? null,
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
  const { path } = await context.params;
  const target = new URL(
    `/v1/${path.map(encodeURIComponent).join("/")}`,
    config.apiUrl,
  );
  const headers = new Headers({
    Authorization: `Bearer ${session}`,
    "X-Autobots-Internal": config.internalToken,
  });
  const contentType = request.headers.get("content-type");
  if (contentType !== null) {
    headers.set("Content-Type", contentType);
  }
  try {
    const body =
      request.method === "GET" || request.method === "HEAD"
        ? null
        : await request.arrayBuffer();
    const reply = await fetch(target, {
      method: request.method,
      headers,
      redirect: "error",
      signal: AbortSignal.timeout(10_000),
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

export const GET = forward;
export const POST = forward;
export const PUT = forward;
export const PATCH = forward;
export const DELETE = forward;
