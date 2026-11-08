import "server-only";

import { NextResponse, type NextRequest } from "next/server";

import { CSRF_COOKIE, CSRF_HEADER, guardRequest } from "@/lib/request-guard";
import { serverConfig } from "@/lib/server-config";
import { accessToken } from "@/lib/session";
import { chosenWorkspace, WORKSPACE_HEADER } from "@/lib/workspace-choice";

const MAX_BODY_BYTES = 64 * 1024;
// A goal may carry up to five attached text files of 1 MiB each (PRD-Tool-Catalog FI-01), which
// JSON escaping can grow. Only run creation gets this; every other route keeps the small limit.
const RUN_BODY_BYTES = 12 * 1024 * 1024;

function bodyLimit(method: string, apiPath: string): number {
  return method === "POST" && apiPath.split("?")[0] === "/v1/runs"
    ? RUN_BODY_BYTES
    : MAX_BODY_BYTES;
}

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
async function authorized(
  request: NextRequest,
): Promise<Headers | NextResponse> {
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
  // Decision 0023 E3: the chosen workspace, which the API checks against membership.
  const workspace = await chosenWorkspace();
  if (workspace !== null) {
    headers.set(WORKSPACE_HEADER, workspace);
  }
  return headers;
}

export async function forward(
  request: NextRequest,
  apiPath: string,
): Promise<NextResponse> {
  const config = serverConfig();
  const headers = await authorized(request);
  if (headers instanceof NextResponse) {
    return headers;
  }
  for (const name of [
    "content-type",
    "x-autobots-workspace",
    "idempotency-key",
  ]) {
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
    if (body !== null && body.byteLength > bodyLimit(request.method, apiPath)) {
      return safeError(413, "request_too_large", "This request is too large.");
    }
    const reply = await fetch(new URL(apiPath, config.apiUrl), {
      method: request.method,
      headers,
      redirect: "error",
      signal: AbortSignal.timeout(30_000),
      ...(body === null ? {} : { body }),
    });
    const replyHeaders = new Headers({
      "Content-Type": reply.headers.get("content-type") ?? "application/json",
      "Cache-Control": "no-store",
    });
    for (const name of ["content-disposition", "x-content-type-options"]) {
      const value = reply.headers.get(name);
      if (value !== null) {
        replyHeaders.set(name, value);
      }
    }
    return new NextResponse(await reply.arrayBuffer(), {
      status: reply.status,
      headers: replyHeaders,
    });
  } catch {
    return safeError(
      503,
      "service_unavailable",
      "The local API is unavailable.",
    );
  }
}

/**
 * A live event stream, passed through unbuffered. The browser going away ends this request and its
 * reader, and nothing else: a run's work belongs to its worker.
 */
export async function streamFrom(
  request: NextRequest,
  apiPath: string,
): Promise<Response> {
  const config = serverConfig();
  const headers = await authorized(request);
  if (headers instanceof NextResponse) {
    return headers;
  }
  const workspace = request.headers.get("x-autobots-workspace");
  if (workspace !== null) {
    headers.set("x-autobots-workspace", workspace);
  }
  try {
    const reply = await fetch(new URL(apiPath, config.apiUrl), {
      headers,
      redirect: "error",
      signal: request.signal,
    });
    if (!reply.ok || reply.body === null) {
      return new NextResponse(await reply.arrayBuffer(), {
        status: reply.status,
        headers: {
          "Content-Type":
            reply.headers.get("content-type") ?? "application/json",
          "Cache-Control": "no-store",
        },
      });
    }
    return new Response(reply.body, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-store",
        "X-Accel-Buffering": "no",
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
