import "server-only";

import { NextResponse, type NextRequest } from "next/server";

import {
  apiHeaders,
  bodyLimit,
  forwardedHeaders,
  relayHeaders,
  routeTemplate,
} from "@/lib/bff-policy";
import {
  failureRefusal,
  guardRefusal,
  NOT_SIGNED_IN,
  TOO_LARGE,
  type Refusal,
} from "@/lib/failure";
import { CSRF_COOKIE, CSRF_HEADER, guardRequest } from "@/lib/request-guard";
import { serverConfig } from "@/lib/server-config";
import { logFailure } from "@/lib/server-log";
import { accessToken } from "@/lib/session";
import { chosenWorkspace } from "@/lib/workspace-choice";

/** The service's `{code, message}` envelope, never cached. Every route answers a refusal with it. */
export function jsonError(refusal: Refusal): NextResponse {
  return NextResponse.json(
    { code: refusal.code, message: refusal.message },
    { status: refusal.status, headers: { "Cache-Control": "no-store" } },
  );
}

/**
 * The same-origin and CSRF check, fed once for every route (WSHL-05). Null lets the request through.
 * Throws `ConfigurationError` when the allowed origin is missing or malformed.
 */
export function refusalFor(request: NextRequest): NextResponse | null {
  const refusal = guardRequest(
    {
      method: request.method,
      host: request.headers.get("host"),
      origin: request.headers.get("origin"),
      fetchSite: request.headers.get("sec-fetch-site"),
      csrfHeader: request.headers.get(CSRF_HEADER),
      csrfCookie: request.cookies.get(CSRF_COOKIE)?.value ?? null,
    },
    { allowedOrigin: serverConfig().allowedOrigin },
  );
  return refusal === null ? null : jsonError(guardRefusal(refusal));
}

/** Logs a caught failure's cause on the server, and answers with its safe class (WSHL-02). */
export function failed(
  operation: string,
  error: unknown,
  service: "api" | "auth" = "api",
): NextResponse {
  logFailure(operation, error);
  return jsonError(failureRefusal(error, service));
}

/**
 * The browser only ever talks to these same-origin routes. The internal token is added here, on the
 * server, and anything the client sent under that name is dropped. Bodies are forwarded unread and
 * never logged, so a draft key cannot reach a response or a log from this layer.
 */
async function authorized(
  request: NextRequest,
): Promise<Headers | NextResponse> {
  const refused = refusalFor(request);
  if (refused !== null) {
    return refused;
  }
  const session = await accessToken();
  if (session === null) {
    return jsonError(NOT_SIGNED_IN);
  }
  // The chosen workspace, which the API checks against membership (Decision 0023 E3).
  const workspace = await chosenWorkspace();
  return forwardedHeaders(
    request.headers,
    apiHeaders(serverConfig().internalToken, session, workspace),
  );
}

/**
 * Every failure, including the checks before the request is sent, is logged and answered with the
 * envelope: missing configuration and an Auth outage are 503 with their own codes, this layer's
 * 30-second timeout is 504 `upstream_timeout`, and anything else is 503 `service_unavailable`.
 */
export async function forward(
  request: NextRequest,
  apiPath: string,
): Promise<NextResponse> {
  try {
    const headers = await authorized(request);
    if (headers instanceof NextResponse) {
      return headers;
    }
    const body =
      request.method === "GET" || request.method === "HEAD"
        ? null
        : await request.arrayBuffer();
    if (body !== null && body.byteLength > bodyLimit(request.method, apiPath)) {
      return jsonError(TOO_LARGE);
    }
    const reply = await fetch(new URL(apiPath, serverConfig().apiUrl), {
      method: request.method,
      headers,
      redirect: "error",
      signal: AbortSignal.timeout(30_000),
      ...(body === null ? {} : { body }),
    });
    return new NextResponse(await reply.arrayBuffer(), {
      status: reply.status,
      headers: relayHeaders(reply.headers),
    });
  } catch (error) {
    return failed(`${request.method} ${routeTemplate(apiPath)}`, error);
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
  try {
    const headers = await authorized(request);
    if (headers instanceof NextResponse) {
      return headers;
    }
    const reply = await fetch(new URL(apiPath, serverConfig().apiUrl), {
      headers,
      redirect: "error",
      signal: request.signal,
    });
    if (!reply.ok || reply.body === null) {
      return new NextResponse(await reply.arrayBuffer(), {
        status: reply.status,
        headers: relayHeaders(reply.headers),
      });
    }
    return new Response(reply.body, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-store",
        "X-Accel-Buffering": "no",
      },
    });
  } catch (error) {
    // The browser left before the stream began, so nothing failed and nobody reads the answer.
    if (request.signal.aborted) {
      return jsonError(failureRefusal(error));
    }
    return failed(`${request.method} ${routeTemplate(apiPath)}`, error);
  }
}
