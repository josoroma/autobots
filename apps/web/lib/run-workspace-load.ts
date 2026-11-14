/**
 * The run page's load states, built on the read classification in `load.ts` (WRUN-02, WRUN-04). A
 * refusal or a contract mismatch stops the page, since reading again can't change it; an outage is
 * tried again after a growing wait; and a snapshot read before the one shown never replaces it. Runs
 * in the browser and under `node --test`; `run-connection.ts` drives it.
 */
import { backoff, type LoadFailure } from "./load.ts";

/** The stream's state while a snapshot is shown, as `data-connection` names it. */
export type Connection = "loading" | "live" | "reconnecting" | "ended";

/**
 * What the run page shows. `retrying` is an outage before any snapshot arrived, with the attempt that
 * failed and the wait before the next; with a snapshot shown, an outage is `ready` and reconnecting.
 * `invalid` is a reply that doesn't match the contract, named by its schema and path, never a value.
 */
export type WorkspaceLoad<S> =
  | { kind: "loading" }
  | { kind: "ready"; snapshot: S; connection: Connection }
  | {
      kind: "retrying";
      attempt: number;
      delayMs: number;
      status: number | null;
    }
  | { kind: "signed_out" }
  | { kind: "denied"; message: string | null }
  | { kind: "not_found" }
  | { kind: "invalid"; schema: string | null; path: string };

/** What a stopped page says for a run that is missing or out of reach (PRD-Development-Harness DH-06). */
export const RUN_NOT_FOUND =
  "That run is not available. Sign in with access to it, or check the link.";

const RETRY_BASE_MS = 1000;
const RETRY_CAP_MS = 30_000;

/** The wait after `failures` failed attempts in a row: 1 s, 2 s, 4 s and so on, up to 30 s. */
export function retryDelay(failures: number): number {
  return backoff(failures, RETRY_BASE_MS, RETRY_CAP_MS);
}

/** Whether a failure ends the page's reading. Only an outage is tried again. */
export function stops(failure: LoadFailure): boolean {
  return failure.kind !== "unavailable";
}

function stopped<S>(load: WorkspaceLoad<S>): boolean {
  return (
    load.kind !== "loading" && load.kind !== "ready" && load.kind !== "retrying"
  );
}

/**
 * The page after a snapshot read. One older than the snapshot shown is discarded; an equal cursor is
 * applied, since figures such as usage can change without an event. The cursor is the run's event
 * sequence when the snapshot was read (run_projection.py).
 */
export function withSnapshot<S extends { cursor: number }>(
  load: WorkspaceLoad<S>,
  snapshot: S,
): WorkspaceLoad<S> {
  if (stopped(load)) return load;
  if (load.kind !== "ready") {
    return { kind: "ready", snapshot, connection: "loading" };
  }
  return snapshot.cursor < load.snapshot.cursor ? load : { ...load, snapshot };
}

/**
 * The page after a failed read. A refusal or a mismatch replaces whatever was shown, so nothing read
 * before a sign-out stays on screen. An outage keeps a shown snapshot, reconnecting.
 */
export function withFailure<S>(
  load: WorkspaceLoad<S>,
  failure: LoadFailure,
  retry: { attempt: number; delayMs: number },
): WorkspaceLoad<S> {
  if (stopped(load)) return load;
  switch (failure.kind) {
    case "signed_out":
    case "not_found":
      return { kind: failure.kind };
    case "denied":
      return { kind: "denied", message: failure.message };
    case "out_of_date":
      return { kind: "invalid", schema: failure.schema, path: failure.path };
    case "unavailable":
      return load.kind === "ready"
        ? { ...load, connection: "reconnecting" }
        : { kind: "retrying", ...retry, status: failure.status };
  }
}

/** The page after the stream opens or ends. Only a shown snapshot has a connection. */
export function withConnection<S>(
  load: WorkspaceLoad<S>,
  connection: Connection,
): WorkspaceLoad<S> {
  return load.kind === "ready" ? { ...load, connection } : load;
}

/**
 * What `components/ui/load-state.tsx` shows instead of the run, or null while a snapshot is shown.
 * Retrying is an unavailable read, so it offers Retry.
 */
export function shownState<S>(
  load: WorkspaceLoad<S>,
): { kind: "loading" } | LoadFailure | null {
  switch (load.kind) {
    case "ready":
      return null;
    case "retrying":
      return { kind: "unavailable", status: load.status };
    case "invalid":
      return { kind: "out_of_date", schema: load.schema, path: load.path };
    default:
      return load;
  }
}

/** When the next attempt is, in whole seconds. */
export function retryWords(delayMs: number): string {
  const seconds = Math.round(delayMs / 1000);
  return `Trying again in ${seconds} ${seconds === 1 ? "second" : "seconds"}.`;
}
