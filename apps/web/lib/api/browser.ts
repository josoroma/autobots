/**
 * The browser's client for the service's API, through the BFF's same-origin routes (R-48, XMOD-03,
 * XDUP-06, XTYP-01). Screens call the generated operations with `reads` or `writes`, so a renamed
 * request field, query or path fails to compile rather than failing as a 422. Reads never come from
 * the HTTP cache, and identical reads in flight share one request; writes carry the double-submit
 * token through `csrfFetch`. The BFF still checks the host, origin, token, session and workspace of
 * every call (PRD-Development-Harness DH-06). Runs in the browser and under `node --test`.
 */
import { parseErrorResponse, type ErrorResponse } from "@autobots/api-client";
import {
  HttpFailure,
  requestJson,
  type ClientOptions,
} from "@autobots/api-client/runtime";

import { csrfFetch } from "../csrf-fetch.ts";
import {
  parseSessionState,
  parseWorkspaceChoice,
  type SessionState,
  type SignInRequest,
  type WorkspaceChoice,
} from "./bff-bodies.ts";

const BASE = "/api";
const MODELS = "/api/v1/models";
const SETTINGS = "/api/v1/settings/";

/**
 * The URL the browser asks for. PRD-Model-Providers MP-05 names `GET /api/models` and the
 * `/api/settings/...` routes, which the BFF serves beside the /api/v1 catch-all, so the browser
 * keeps asking for them by those names.
 */
export function bffUrl(url: string): string {
  if (url === MODELS || url.startsWith(`${MODELS}?`)) {
    return `/api/models${url.slice(MODELS.length)}`;
  }
  if (url.startsWith(SETTINGS)) {
    return `/api/settings/${url.slice(SETTINGS.length)}`;
  }
  return url;
}

function urlOf(input: RequestInfo | URL): string {
  if (typeof input === "string") return input;
  return input instanceof URL ? input.href : input.url;
}

/** A read's reply, read once, which each reader gets its own `Response` of. */
interface Copy {
  readonly status: number;
  readonly statusText: string;
  readonly headers: Headers;
  readonly body: ArrayBuffer;
}

interface Flight {
  readonly copy: Promise<Copy>;
  readonly controller: AbortController;
  readers: number;
}

// Identical reads in flight at the same time share one request. A flight is forgotten as soon as
// its body has been read, so no workspace data is kept after a read, or after a sign-out (XWEB-02,
// PRD-Development-Harness DH-06).
const flights = new Map<string, Flight>();

/** How many shared reads are in flight. Zero once every read has settled. */
export function readsInFlight(): number {
  return flights.size;
}

function forget(url: string, flight: Flight): void {
  if (flights.get(url) === flight) flights.delete(url);
}

function join(url: string, fetcher: typeof globalThis.fetch): Flight {
  const current = flights.get(url);
  if (current !== undefined) return current;
  const controller = new AbortController();
  const flight: Flight = {
    controller,
    readers: 0,
    // Reading the body, refusals included, releases the connection. A read declares no headers of
    // its own: the BFF adds the session's and the workspace's.
    copy: fetcher(url, {
      method: "GET",
      cache: "no-store",
      signal: controller.signal,
    }).then(async (reply) => ({
      status: reply.status,
      statusText: reply.statusText,
      headers: reply.headers,
      body: await reply.arrayBuffer(),
    })),
  };
  flights.set(url, flight);
  const settled = () => forget(url, flight);
  flight.copy.then(settled, settled);
  return flight;
}

// Statuses whose reply can't carry a body (Fetch standard, "null body status").
const NO_BODY: ReadonlySet<number> = new Set([204, 205, 304]);

function replyOf(copy: Copy): Response {
  return new Response(NO_BODY.has(copy.status) ? null : copy.body, {
    status: copy.status,
    statusText: copy.statusText,
    headers: copy.headers,
  });
}

/** The shared reply for one reader. A reader that aborts leaves; the last to leave aborts the request. */
function sharedRead(
  fetcher: typeof globalThis.fetch,
  url: string,
  signal: AbortSignal | null,
): Promise<Response> {
  const flight = join(url, fetcher);
  flight.readers += 1;
  if (signal === null) return flight.copy.then(replyOf);
  return new Promise((resolve, reject) => {
    const leave = () => {
      flight.readers -= 1;
      if (flight.readers === 0) {
        flight.controller.abort();
        forget(url, flight);
      }
      reject(new DOMException("The read was aborted.", "AbortError"));
    };
    if (signal.aborted) {
      leave();
      return;
    }
    signal.addEventListener("abort", leave, { once: true });
    flight.copy.then(
      (copy) => {
        signal.removeEventListener("abort", leave);
        resolve(replyOf(copy));
      },
      (error: unknown) => {
        signal.removeEventListener("abort", leave);
        reject(error);
      },
    );
  });
}

export interface ReadOptions {
  /** Aborts this read, such as one a newer read replaced (WRUN-16). */
  signal?: AbortSignal;
  /** For tests. The browser's own fetch otherwise, looked up at each call. */
  fetch?: typeof globalThis.fetch;
}

/** Options for reads: base `/api`, never from the HTTP cache, and shared while in flight. */
export function readClient(options: ReadOptions = {}): ClientOptions {
  return {
    baseUrl: BASE,
    fetch: (input, init) => {
      // Called without a receiver, so the browser's fetch keeps its own.
      const fetcher = options.fetch ?? globalThis.fetch;
      const url = bffUrl(urlOf(input));
      if ((init?.method ?? "GET") !== "GET") {
        return fetcher(url, { ...init, cache: "no-store" });
      }
      return sharedRead(fetcher, url, options.signal ?? init?.signal ?? null);
    },
  };
}

/** Options for a read in a handler, such as a version read before a press. */
export const reads: ClientOptions = readClient();

/** Options for writes: base `/api`, and the double-submit token on each (lib/csrf-fetch.ts). */
export const writes: ClientOptions = {
  baseUrl: BASE,
  fetch: (input, init) => csrfFetch(bffUrl(urlOf(input)), init ?? {}),
};

/** Why a call through this client failed, for a screen's words and a write's outcome (R-02). */
export interface Failure {
  /** The reply's status, or null when none arrived or a success drifted from its contract. */
  status: number | null;
  /** The service's error body, or the BFF's, when the reply carried one. */
  refusal: ErrorResponse | null;
}

export function failureOf(error: unknown): Failure {
  return error instanceof HttpFailure
    ? { status: error.status, refusal: error.envelope }
    : { status: null, refusal: null };
}

/** A generated operation's method and route, without the `/api` base. */
export interface TypedRoute {
  method: "POST" | "PUT";
  path: string;
}

/**
 * A write whose body holds JSON as a person typed it, such as a workflow's graph or an execution's
 * inputs, which only the service validates (PRD-Studio WF-02). Its generated operation can't take
 * an unchecked value, so the caller names the operation's route (lib/workflows/unchecked-writes.ts),
 * and `parse` is the operation's generated reply parser. `key` is its Idempotency-Key, when it
 * declares one.
 */
export async function writeAsTyped<T>(
  route: TypedRoute,
  body: unknown,
  parse: (value: unknown) => T,
  key: string | null = null,
): Promise<T> {
  const request =
    key === null ? undefined : { headers: { "Idempotency-Key": key } };
  return parse(
    await requestJson(
      writes,
      route.method,
      route.path,
      body,
      request,
      parseErrorResponse,
    ),
  );
}

// The BFF's own routes, which the service's contract doesn't hold (lib/api/bff-bodies.ts).

/** Signs in with the session route (app/api/session/route.ts). */
export async function signIn(body: SignInRequest): Promise<SessionState> {
  return parseSessionState(
    await requestJson(
      writes,
      "POST",
      "/session",
      body,
      undefined,
      parseErrorResponse,
    ),
  );
}

/** Signs this device out. */
export async function signOut(): Promise<SessionState> {
  return parseSessionState(
    await requestJson(
      writes,
      "DELETE",
      "/session",
      undefined,
      undefined,
      parseErrorResponse,
    ),
  );
}

/** Chooses the workspace the screens act on (Decision 0023 E3, app/api/workspace/route.ts). */
export async function chooseWorkspace(
  body: WorkspaceChoice,
): Promise<WorkspaceChoice> {
  return parseWorkspaceChoice(
    await requestJson(
      writes,
      "POST",
      "/workspace",
      body,
      undefined,
      parseErrorResponse,
    ),
  );
}

/**
 * A stored artifact as the BFF relays it. Its download route isn't one of the contract's JSON
 * operations, as its body is the file itself, so it has this one call. Never from the HTTP cache.
 */
export function downloadArtifact(
  artifactId: string,
  options: ReadOptions = {},
): Promise<Response> {
  const fetcher = options.fetch ?? globalThis.fetch;
  return fetcher(
    `${BASE}/v1/artifacts/${encodeURIComponent(artifactId)}/download`,
    {
      cache: "no-store",
      ...(options.signal === undefined ? {} : { signal: options.signal }),
    },
  );
}
