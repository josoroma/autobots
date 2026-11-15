/**
 * The account's pure parts, shared by the sidebar footer and Settings → Account (PRD-Studio SH-05
 * and SE-04, Decision 0023 E3, WSHL-18). Pure and JSX-free, so `node --test` covers it.
 */

/** A workspace role in words. */
export const ROLE_LABEL = { owner: "Owner", member: "Member" } as const;

/** Up to two letters for the avatar: the first of two names, or the first two of one. */
export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const letters = parts.length > 1 ? [parts[0], parts[1]] : [name.trim()];
  return letters
    .map((part) => (part ?? "").slice(0, parts.length > 1 ? 1 : 2))
    .join("")
    .toUpperCase();
}

/**
 * Decision 0023 E3: the chooser shows for a member of several workspaces, or when the choice no
 * longer names the current workspace, such as one the person has left. `current` is what
 * `currentWorkspace` resolved for this choice.
 */
export function choosingWorkspace(
  workspaces: readonly { id: string }[],
  chosen: string | null,
  current: { id: string } | null,
): boolean {
  return workspaces.length > 1 || (chosen !== null && current?.id !== chosen);
}
