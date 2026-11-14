import "server-only";

import { cookies } from "next/headers";

// Decision 0023 E3: which workspace a member of several is working in. Kept in an HttpOnly cookie that
// only /api/workspace sets, after checking membership. The API checks membership again on every call.
export const WORKSPACE_COOKIE = "autobots.workspace";

const IDENTIFIER =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isWorkspaceId(value: unknown): value is string {
  return typeof value === "string" && IDENTIFIER.test(value);
}

/** The chosen workspace, or null when none is chosen or the cookie isn't an identifier. */
export async function chosenWorkspace(): Promise<string | null> {
  const value = (await cookies()).get(WORKSPACE_COOKIE)?.value;
  return isWorkspaceId(value) ? value : null;
}

/** The workspace screens act on: the only one, or the chosen one when the person belongs to it. */
export function currentWorkspace<T extends { id: string }>(
  workspaces: readonly T[],
  chosen: string | null,
): T | null {
  if (workspaces.length === 1) {
    return workspaces[0] ?? null;
  }
  return workspaces.find((workspace) => workspace.id === chosen) ?? null;
}
