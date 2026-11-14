/**
 * One read's outcome, classified the same way for every screen, so a contract mismatch is told from
 * an outage, a refusal and a signed-out session (XERR-03, XERR-04, XTYP-14). Runs in the browser and
 * under `node --test`; `use-resource.ts` drives it from React and `components/ui/load-state.tsx`
 * renders it.
 */
import { parseErrorResponse } from "@autobots/api-client";
import {
  ContractError,
  HttpFailure,
  requestJson,
} from "@autobots/api-client/runtime";

/**
 * Why a read has no value. `denied` carries the service's own message when its reply had one.
 * `unavailable` covers a 5xx, any refusal not named here and no reply at all (`status: null`), and
 * a read can be retried safely. `out_of_date` names the contract and the field that failed; a reply
 * that isn't JSON has no schema, and its `path` is the route without the query string, which can
 * carry what a person typed.
 */
export type LoadFailure =
  | { kind: "signed_out" }
  | { kind: "denied"; message: string | null }
  | { kind: "not_found" }
  | { kind: "unavailable"; status: number | null }
  | { kind: "out_of_date"; schema: string | null; path: string };

export type Loaded<T> = { kind: "ready"; value: T } | LoadFailure;

export interface LoadOptions {
  signal?: AbortSignal;
  /** For tests. The browser's own fetch otherwise. */
  fetch?: typeof globalThis.fetch;
}

/** The out-of-date sentence, fixed so a person sees the same words on every screen. */
export const OUT_OF_DATE =
  "This page and the local service disagree. Reload after updating.";

// The same bound the server's failure record keeps (lib/failure.ts).
const PATH_LIMIT = 200;

interface Flight {
  readonly body: Promise<unknown>;
  readonly controller: AbortController;
  readers: number;
}

// Identical GETs in flight at the same time share one request. A flight is forgotten as soon as it
// settles, so no workspace data is kept after a read, or after a sign-out (XWEB-02,
// PRD-Development-Harness DH-06).
const flights = new Map<string, Flight>();

/** How many shared reads are in flight. Zero once every read has settled. */
export function readsInFlight(): number {
  return flights.size;
}

function forget(path: string, flight: Flight): void {
  if (flights.get(path) === flight) flights.delete(path);
}

function join(path: string, fetcher: typeof globalThis.fetch): Flight {
  const current = flights.get(path);
  if (current !== undefined) return current;
  const controller = new AbortController();
  // Called without a receiver, so the browser's fetch keeps its own.
  const noStore: typeof globalThis.fetch = (input, init) =>
    fetcher(input, { ...init, cache: "no-store" });
  const flight: Flight = {
    controller,
    readers: 0,
    // The error parser makes requestJson read a refused body, which releases its connection.
    body: requestJson(
      { baseUrl: "", fetch: noStore },
      "GET",
      path,
      undefined,
      { signal: controller.signal },
      parseErrorResponse,
    ),
  };
  flights.set(path, flight);
  const settled = () => forget(path, flight);
  flight.body.then(settled, settled);
  return flight;
}

/** The shared body for one reader. A reader that aborts leaves; the last to leave aborts the request. */
function read(path: string, options: LoadOptions): Promise<unknown> {
  const flight = join(path, options.fetch ?? globalThis.fetch);
  flight.readers += 1;
  const signal = options.signal;
  if (signal === undefined) return flight.body;
  return new Promise((resolve, reject) => {
    const leave = () => {
      flight.readers -= 1;
      if (flight.readers === 0) {
        flight.controller.abort();
        forget(path, flight);
      }
      reject(new DOMException("The read was aborted.", "AbortError"));
    };
    if (signal.aborted) {
      leave();
      return;
    }
    signal.addEventListener("abort", leave, { once: true });
    flight.body.then(
      (value) => {
        signal.removeEventListener("abort", leave);
        resolve(value);
      },
      (error: unknown) => {
        signal.removeEventListener("abort", leave);
        reject(error);
      },
    );
  });
}

function refusal(error: unknown): LoadFailure {
  if (!(error instanceof HttpFailure))
    return { kind: "unavailable", status: null };
  switch (error.status) {
    case 401:
      return { kind: "signed_out" };
    case 403:
      return { kind: "denied", message: error.envelope?.message ?? null };
    case 404:
    case 422:
      return { kind: "not_found" };
    default:
      return { kind: "unavailable", status: error.status };
  }
}

function mismatch(error: ContractError): LoadFailure {
  const path = error.path.slice(0, PATH_LIMIT);
  return {
    kind: "out_of_date",
    schema: path.split(/[.[]/, 1)[0] ?? path,
    path,
  };
}

/**
 * Reads `path` from this origin and parses it. Never throws: every outcome is a `Loaded`. A caller
 * that aborted discards the result, which then reads as unavailable.
 */
export async function loadJson<T>(
  path: string,
  parse: (value: unknown) => T,
  options: LoadOptions = {},
): Promise<Loaded<T>> {
  let body: unknown;
  try {
    body = await read(path, options);
  } catch (error) {
    // requestJson's only ContractError is a 2xx body that isn't JSON.
    return error instanceof ContractError
      ? {
          kind: "out_of_date",
          schema: null,
          path: (path.split("?", 1)[0] ?? "").slice(0, PATH_LIMIT),
        }
      : refusal(error);
  }
  try {
    return { kind: "ready", value: parse(body) };
  } catch (error) {
    return error instanceof ContractError
      ? mismatch(error)
      : { kind: "unavailable", status: null };
  }
}

/**
 * What the browser console records for a mismatch: the schema and the field's path, never a value
 * from the reply (XTYP-14); a path can include a key of a map-typed field. Null for any other outcome.
 */
export function mismatchRecord(failure: LoadFailure): {
  event: "web.contract_mismatch";
  schema: string | null;
  path: string;
} | null {
  return failure.kind === "out_of_date"
    ? {
        event: "web.contract_mismatch",
        schema: failure.schema,
        path: failure.path,
      }
    : null;
}

function capitalized(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/**
 * The fixed words for a failure, given what was being read as a noun phrase such as "runs" or
 * "this tool". Only an unavailable read offers Retry; the rest need a person to act elsewhere.
 */
export function failureWords(
  failure: LoadFailure,
  what: string,
): { words: string; retry: boolean } {
  switch (failure.kind) {
    case "signed_out":
      return {
        words: `You're signed out. Sign in to see ${what}.`,
        retry: false,
      };
    case "denied":
      return {
        words: failure.message ?? `You don't have access to ${what}.`,
        retry: false,
      };
    case "not_found":
      return { words: `${capitalized(what)} can't be found.`, retry: false };
    case "out_of_date":
      return { words: OUT_OF_DATE, retry: false };
    case "unavailable":
      return {
        words: `${capitalized(what)} can't be read right now. Check that the local services are running, then try again.`,
        retry: true,
      };
  }
}

// What the person must act on first: signing in, then access, then updating, then a missing thing.
const PRECEDENCE: readonly LoadFailure["kind"][] = [
  "signed_out",
  "denied",
  "out_of_date",
  "not_found",
  "unavailable",
];

/**
 * The failure to show for several reads on one screen, or null when none has failed. A state is a
 * read's `Loaded`, or a hook's loading or idle state, which never fails.
 */
export function worstFailure(
  states: readonly { kind: string }[],
): LoadFailure | null {
  const failures = states.filter((state): state is LoadFailure =>
    PRECEDENCE.some((kind) => kind === state.kind),
  );
  for (const kind of PRECEDENCE) {
    const found = failures.find((failure) => failure.kind === kind);
    if (found !== undefined) return found;
  }
  return null;
}

/** A poll's delay after `failures` failed reads in a row: `base`, doubling, up to `cap`. */
export function backoff(failures: number, base: number, cap: number): number {
  return Math.min(cap, base * 2 ** Math.max(0, failures - 1));
}
