import { NextResponse, type NextRequest } from "next/server";

import { failed, jsonError, refusalFor } from "@/lib/bff";
import { cookieOptions, readJsonObject } from "@/lib/bff-policy";
import { API_UNAVAILABLE, NOT_SIGNED_IN } from "@/lib/failure";
import { serverConfig } from "@/lib/server-config";
import { fetchSession } from "@/lib/service-status";
import { isWorkspaceId, WORKSPACE_COOKIE } from "@/lib/workspace-choice";

const INVALID_WORKSPACE = {
  status: 422,
  code: "invalid_workspace",
  message: "Choose one of your workspaces.",
};
const NOT_A_MEMBER = {
  status: 403,
  code: "forbidden",
  message: "This workspace is not available.",
};

/**
 * Decision 0023 E3: choose the workspace. Same origin and CSRF-checked, signed in, and only a
 * workspace the verified session belongs to. The API still checks membership on every request.
 * A session the API can't read is 503, never a prompt to sign in (WSHL-02).
 */
export async function POST(request: NextRequest): Promise<NextResponse> {
  try {
    const refused = refusalFor(request);
    if (refused !== null) {
      return refused;
    }
    const chosen = (await readJsonObject(request))?.workspace_id;
    if (!isWorkspaceId(chosen)) {
      return jsonError(INVALID_WORKSPACE);
    }
    const session = await fetchSession();
    if (session.kind === "signed_out") {
      return jsonError(NOT_SIGNED_IN);
    }
    if (session.kind === "unavailable") {
      return jsonError(API_UNAVAILABLE);
    }
    if (!session.value.workspace_ids.includes(chosen)) {
      return jsonError(NOT_A_MEMBER);
    }
    const reply = NextResponse.json(
      { workspace_id: chosen },
      { headers: { "Cache-Control": "no-store" } },
    );
    reply.cookies.set(
      WORKSPACE_COOKIE,
      chosen,
      cookieOptions(serverConfig().allowedOrigin, true),
    );
    return reply;
  } catch (error) {
    return failed("workspace.choose", error);
  }
}
