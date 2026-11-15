"use client";

import { Plus } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useCallback } from "react";

import { NEW_RUN_SHORTCUT } from "@/lib/shortcuts";
import { useShortcut } from "@/lib/use-shortcut";

export const NEW_RUN_PARAM = "new";

export function focusGoal(): void {
  const goal = document.getElementById("goal");
  goal?.focus();
  goal?.scrollIntoView({ block: "center" });
}

// PRD-Studio SH-02 and Decision 0022 D16: ⇧⌘O, or this button right after the skip link, opens Home's
// composer with focus in the goal. Nothing is sent, and the shortcut does nothing in a text field.
export function NewRun() {
  const router = useRouter();
  const path = usePathname();

  const open = useCallback(() => {
    if (path === "/") focusGoal();
    else router.push(`/?${NEW_RUN_PARAM}=1`);
  }, [path, router]);
  useShortcut(NEW_RUN_SHORTCUT.matches, open);

  return (
    <button
      type="button"
      onClick={open}
      aria-keyshortcuts={NEW_RUN_SHORTCUT.aria}
      data-field="new-run-button"
      className="text-sidebar-foreground hover:bg-sidebar-accent border-sidebar-border flex w-full items-center gap-2 rounded-lg border px-2.5 py-1.5 text-ui font-medium"
    >
      <Plus aria-hidden="true" className="size-3.5 shrink-0" />
      <span className="flex-1 text-left">New run</span>
      <kbd
        aria-hidden="true"
        className="text-muted-foreground border-sidebar-border rounded border px-1 font-mono text-kbd"
      >
        {NEW_RUN_SHORTCUT.keys.join("")}
      </kbd>
    </button>
  );
}
