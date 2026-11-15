/**
 * One read's outcome, classified the same way for every screen, so a contract mismatch is told from
 * an outage, a refusal and a signed-out session (XERR-03, XERR-04, XTYP-14). A read is a generated
 * operation called with the browser's read client (R-48). Runs in the browser and under
 * `node --test`; `use-resource.ts` drives it from React and `components/ui/load-state.tsx` renders
 * it.
 */
import {
  ContractError,
  HttpFailure,
  type ClientOptions,
} from "@autobots/api-client/runtime";

import { readClient, type ReadOptions } from "./api/browser.ts";

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

export type LoadOptions = ReadOptions;

/**
 * A read: a generated operation, or a module-level function shaped like one, with the arguments
 * that follow its client.
 */
export interface Read<T> {
  readonly operation: object;
  /** The arguments as JSON, which with the operation tells two reads apart. */
  readonly key: string;
  readonly run: (client: ClientOptions) => Promise<T>;
}

/**
 * A read of `operation` with `args`. One built again on a re-render, from the same operation and
 * arguments, is the same read (`sameRead`), so a re-render reads nothing again.
 */
export function readOf<A extends unknown[], T>(
  operation: (client: ClientOptions, ...args: A) => Promise<T>,
  ...args: A
): Read<T> {
  return {
    operation,
    key: JSON.stringify(args),
    run: (client) => operation(client, ...args),
  };
}

/** Whether two reads ask for the same thing: the same operation, with equal arguments. */
export function sameRead(
  first: Read<unknown> | null,
  second: Read<unknown> | null,
): boolean {
  if (first === null || second === null) return first === second;
  return first.operation === second.operation && first.key === second.key;
}

/**
 * The read a hook keeps after a render that asks for `wanted`: the one it kept, while `wanted` asks
 * for the same thing, so a re-render that builds an equal read reads nothing again, or else
 * `wanted`. `useResource` reads again only when this returns a different read.
 */
export function keptRead<T>(
  kept: Read<T> | null,
  wanted: Read<T> | null,
): Read<T> | null {
  return sameRead(kept, wanted) ? kept : wanted;
}

/** The out-of-date sentence, fixed so a person sees the same words on every screen. */
export const OUT_OF_DATE =
  "This page and the local service disagree. Reload after updating.";

// The same bound the server's failure record keeps (lib/failure.ts).
const PATH_LIMIT = 200;

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

/**
 * A drifted reply names its schema and field. A reply that isn't JSON names its route, which
 * starts with a slash and has no query (packages/api-client/src/runtime.ts).
 */
function mismatch(error: ContractError): LoadFailure {
  const path = error.path.slice(0, PATH_LIMIT);
  return {
    kind: "out_of_date",
    schema: path.startsWith("/") ? null : (path.split(/[.[]/, 1)[0] ?? path),
    path,
  };
}

/**
 * Runs `source` with the read client and classifies the outcome. Never throws: every outcome is a
 * `Loaded`. A caller that aborted discards the result, which then reads as unavailable.
 */
export async function load<T>(
  source: Read<T>,
  options: LoadOptions = {},
): Promise<Loaded<T>> {
  try {
    return { kind: "ready", value: await source.run(readClient(options)) };
  } catch (error) {
    return error instanceof ContractError ? mismatch(error) : refusal(error);
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
