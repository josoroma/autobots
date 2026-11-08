import { ChevronUp, Laptop } from "lucide-react";
import Link from "next/link";

import { SignOutButton } from "@/components/sign-out-button";
import { fetchSession } from "@/lib/service-status";

const ROLE = { owner: "Owner", member: "Member" } as const;

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const letters = parts.length > 1 ? [parts[0], parts[1]] : [name.trim()];
  return letters
    .map((part) => (part ?? "").slice(0, parts.length > 1 ? 1 : 2))
    .join("")
    .toUpperCase();
}

// PRD-Studio SH-05: the display name, the role in the current workspace and "this Mac", with a
// menu offering Settings → Account and Sign out. The current workspace is the session's first one.
export async function AccountFooter() {
  const session = await fetchSession();
  if (session === null) {
    return (
      <div className="border-sidebar-border border-t px-2 pt-3">
        <Link
          href="/sign-in"
          className="text-sidebar-foreground text-sm font-medium underline"
        >
          Sign in
        </Link>
      </div>
    );
  }
  const workspace = session.workspaces[0];
  return (
    <details
      data-account
      className="border-sidebar-border group relative border-t pt-3"
    >
      <summary className="hover:bg-sidebar-accent flex cursor-pointer list-none items-center gap-2.5 rounded-lg px-2 py-1.5 [&::-webkit-details-marker]:hidden">
        <span
          aria-hidden="true"
          className="bg-sidebar-accent text-sidebar-accent-foreground grid size-8 shrink-0 place-items-center rounded-full text-xs font-semibold"
        >
          {initials(session.display_name)}
        </span>
        <span className="min-w-0 flex-1 leading-tight">
          <span
            data-field="display-name"
            className="block truncate text-sm font-medium"
          >
            {session.display_name}
          </span>
          <span className="text-muted-foreground flex items-center gap-1.5 text-xs">
            <Laptop aria-hidden="true" className="size-3.5" />
            <span data-field="role">
              {workspace === undefined ? "No workspace" : ROLE[workspace.role]}
            </span>
            <span aria-hidden="true">·</span>
            this Mac
          </span>
        </span>
        <ChevronUp
          aria-hidden="true"
          className="text-muted-foreground size-4 shrink-0 transition-transform group-open:rotate-180"
        />
        <span className="sr-only">Account menu</span>
      </summary>
      <div className="bg-popover text-popover-foreground border-border absolute right-0 bottom-full left-0 mb-2 space-y-1 rounded-xl border p-1.5 shadow-lg">
        <Link
          href="/settings/account"
          className="hover:bg-accent hover:text-accent-foreground block rounded-lg px-3 py-2 text-sm"
        >
          Account
        </Link>
        <SignOutButton className="w-full justify-start" />
      </div>
    </details>
  );
}
