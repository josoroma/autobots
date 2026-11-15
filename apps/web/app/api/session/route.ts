import { NextResponse, type NextRequest } from "next/server";

import { readSignInRequest, type SessionState } from "@/lib/api/bff-bodies";
import { failed, jsonError, refusalFor } from "@/lib/bff";
import { readJsonObject } from "@/lib/bff-policy";
import { SIGN_IN_FAILED, signInRefusal } from "@/lib/failure";
import { logFailure } from "@/lib/server-log";
import { sessionClient } from "@/lib/session";
import { WORKSPACE_COOKIE } from "@/lib/workspace-choice";

const SIGN_OUT_FAILED = {
  status: 503,
  code: "sign_out_failed",
  message: "Signing out did not finish. Try again.",
};

/**
 * Sign in. A 401 means Auth refused the credentials and never says which field; an Auth outage is
 * 503 `auth_unavailable`, logged without the email or password (WSHL-07).
 */
export async function POST(request: NextRequest): Promise<NextResponse> {
  try {
    const refused = refusalFor(request);
    if (refused !== null) {
      return refused;
    }
    const credentials = readSignInRequest(await readJsonObject(request));
    if (credentials === null) {
      return jsonError(SIGN_IN_FAILED);
    }
    const client = await sessionClient();
    const { error } = await client.auth.signInWithPassword(credentials);
    if (error === null) {
      return NextResponse.json({ signed_in: true } satisfies SessionState);
    }
    const refusal = signInRefusal(error);
    if (refusal !== SIGN_IN_FAILED) {
      logFailure("auth.sign_in", error);
    }
    return jsonError(refusal);
  } catch (error) {
    return failed("auth.sign_in", error, "auth");
  }
}

/**
 * Sign out of this device. With `scope: "local"`, Auth removes the local session before it asks the
 * server to revoke it (@supabase/auth-js `_signOut`), so a revocation that fails is logged and the
 * device is still signed out. Only a session that is still there is a failure the person sees
 * (WSHL-07).
 */
export async function DELETE(request: NextRequest): Promise<NextResponse> {
  try {
    const refused = refusalFor(request);
    if (refused !== null) {
      return refused;
    }
    const client = await sessionClient();
    const { error } = await client.auth.signOut({ scope: "local" });
    if (error !== null) {
      logFailure("auth.sign_out", error);
      const { data } = await client.auth.getSession();
      if (data.session !== null) {
        return jsonError(SIGN_OUT_FAILED);
      }
    }
    const reply = NextResponse.json({
      signed_in: false,
    } satisfies SessionState);
    reply.cookies.delete(WORKSPACE_COOKIE);
    return reply;
  } catch (error) {
    return failed("auth.sign_out", error, "auth");
  }
}
