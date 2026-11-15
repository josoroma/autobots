/**
 * One read's outcome, classified the same way for every screen, so a contract mismatch is told from
 * an outage, a refusal and a signed-out session (XERR-03, XERR-04, XTYP-14). A read is a generated
 * operation called with the browser's read client (R-48). Runs in the browser and under
 * `node --test`; `use-resource.ts` drives it from React and `components/ui/load-state.tsx` renders
 * it.
 */
import type { ClientOptions } from "@autobots/api-client/runtime";

import { readClient, type ReadOptions } from "./api/browser.ts";
import { loadFailure, type LoadFailure, type Loaded } from "./load-failure.ts";

// The classification is shared with the server's reads (lib/server-api.ts, R-67).
export type { LoadFailure, Loaded } from "./load-failure.ts";
export { worstFailure } from "./load-failure.ts";

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
    return loadFailure(error);
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

/** A poll's delay after `failures` failed reads in a row: `base`, doubling, up to `cap`. */
export function backoff(failures: number, base: number, cap: number): number {
  return Math.min(cap, base * 2 ** Math.max(0, failures - 1));
}
