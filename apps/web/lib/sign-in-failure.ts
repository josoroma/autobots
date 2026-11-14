/**
 * What the sign-in form says about a reply that isn't a success. Only the session route's 401 is
 * about the credentials; a refusal asks for a reload, and an outage or no reply says sign-in is
 * unavailable, so nobody resets a password because Auth is down (WSHL-07).
 */
export type SignInFailure = "credentials" | "refused" | "unavailable";

export const SIGN_IN_FAILURE_TEXT: Readonly<Record<SignInFailure, string>> = {
  credentials: "That email and password did not work.",
  refused: "This request was refused. Reload the page, then sign in again.",
  unavailable:
    "Signing in is unavailable right now. Check that the local services are running, then try again.",
};

/** `status` is null when no reply arrived. */
export function signInFailure(status: number | null): SignInFailure {
  if (status === 401) return "credentials";
  return status === 403 ? "refused" : "unavailable";
}
