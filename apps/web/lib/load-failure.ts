/**
 * Why a read has no value, classified the same way in the browser (`lib/load.ts`) and in a Server
 * Component (`lib/server-api.ts`), so a contract mismatch is told from an outage, a refusal and a
 * signed-out session wherever the read ran (XERR-03, XERR-04, XTYP-14, R-67). Pure, so `node --test`
 * covers it, and the server never imports the browser's client to classify a failure.
 */
import { ContractError, HttpFailure } from "@autobots/api-client/runtime";

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

/** The failure a caught error stands for: the R-02 status, a contract mismatch, or no reply. */
export function loadFailure(error: unknown): LoadFailure {
  return error instanceof ContractError ? mismatch(error) : refusal(error);
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
