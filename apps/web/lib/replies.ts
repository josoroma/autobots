/**
 * A reply's body, read through the generated parsers (R-09, STD-10). A cast let a renamed field
 * compile and fail quietly, such as a success link to /runs/undefined.
 */
import { parseErrorResponse, type ErrorResponse } from "@autobots/api-client";

/** The service's refusal body, or null for anything else, such as a proxy's HTML page. */
export async function readErrorResponse(
  reply: Response | null,
): Promise<ErrorResponse | null> {
  if (reply === null) return null;
  const body: unknown = await reply.json().catch(() => undefined);
  try {
    return parseErrorResponse(body);
  } catch {
    return null;
  }
}

/** A success body, or null when it is missing, not JSON, or drifted from its contract. */
export async function readReply<T>(
  reply: Response,
  parse: (value: unknown) => T,
): Promise<T | null> {
  const body: unknown = await reply.json().catch(() => undefined);
  try {
    return parse(body);
  } catch {
    return null;
  }
}
