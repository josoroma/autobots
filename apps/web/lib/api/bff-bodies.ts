/**
 * The BFF's own bodies: signing in and out, choosing a workspace, and the double-submit token
 * (R-48, XTYP-01). The service's contract doesn't hold them, so these small parsers stand in for
 * generated ones, and the browser and the route handlers share them. Pure and JSX-free.
 */
import { ContractError } from "@autobots/api-client/runtime";

/** `POST /api/session`. */
export interface SignInRequest {
  email: string;
  password: string;
}

/** The reply to signing in or out. */
export interface SessionState {
  signed_in: boolean;
}

/** `POST /api/workspace`, and its reply. */
export interface WorkspaceChoice {
  workspace_id: string;
}

/** `GET /api/csrf`: the header a write carries, and the token it carries in it. */
export interface CsrfToken {
  header: string;
  token: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function text(
  value: Record<string, unknown>,
  field: string,
  name: string,
): string {
  const found = value[field];
  if (typeof found !== "string")
    throw new ContractError(`${name}.${field}`, "not a string");
  return found;
}

/**
 * Sign-in's credentials, or null unless both are non-empty strings. Any other field is ignored, and
 * a null answers with the same refusal as a wrong password, which never says which field failed.
 */
export function readSignInRequest(value: unknown): SignInRequest | null {
  if (!isRecord(value)) return null;
  const { email, password } = value;
  return typeof email === "string" &&
    typeof password === "string" &&
    email !== "" &&
    password !== ""
    ? { email, password }
    : null;
}

/** The chosen workspace, or null when the body names none. The route checks it's a member's. */
export function readWorkspaceChoice(value: unknown): WorkspaceChoice | null {
  return isRecord(value) && typeof value.workspace_id === "string"
    ? { workspace_id: value.workspace_id }
    : null;
}

/** The BFF's reply to signing in or out. A `ContractError` when it isn't one. */
export function parseSessionState(value: unknown): SessionState {
  if (!isRecord(value))
    throw new ContractError("SessionState", "not an object");
  if (typeof value.signed_in !== "boolean")
    throw new ContractError("SessionState.signed_in", "not a boolean");
  return { signed_in: value.signed_in };
}

/** The BFF's reply to choosing a workspace. A `ContractError` when it isn't one. */
export function parseWorkspaceChoice(value: unknown): WorkspaceChoice {
  if (!isRecord(value))
    throw new ContractError("WorkspaceChoice", "not an object");
  return { workspace_id: text(value, "workspace_id", "WorkspaceChoice") };
}

/** The BFF's double-submit token. A `ContractError` when it isn't one. */
export function parseCsrfToken(value: unknown): CsrfToken {
  if (!isRecord(value)) throw new ContractError("CsrfToken", "not an object");
  return {
    header: text(value, "header", "CsrfToken"),
    token: text(value, "token", "CsrfToken"),
  };
}
