import "server-only";

import { failureRecord } from "@/lib/failure";

/**
 * One JSON line on the server's stderr per classified failure, so the cause of an unavailable state
 * stays in a private log (PRD-Development-Harness DH-06, WSHL-02). `failureRecord` keeps it to the
 * operation, the error class, a `ContractError` path, the status and whether a timeout fired.
 */
export function logFailure(operation: string, error: unknown): void {
  console.error(JSON.stringify(failureRecord(operation, error, new Date())));
}
