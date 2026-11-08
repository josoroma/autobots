"use client";

import { Plus } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { typing } from "@/lib/keyboard";

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

  useEffect(() => {
    function open(): void {
      if (path === "/") focusGoal();
      else router.push(`/?${NEW_RUN_PARAM}=1`);
    }
    function onKey(event: KeyboardEvent): void {
      if (
        event.shiftKey &&
        (event.metaKey || event.ctrlKey) &&
        !event.altKey &&
        event.code === "KeyO" &&
        !typing(event.target)
      ) {
        event.preventDefault();
        open();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [path, router]);

  return (
    <button
      type="button"
      onClick={() =>
        path === "/" ? focusGoal() : router.push(`/?${NEW_RUN_PARAM}=1`)
      }
      aria-keyshortcuts="Shift+Meta+O Shift+Control+O"
      data-field="new-run-button"
      className="text-sidebar-foreground hover:bg-sidebar-accent border-sidebar-border flex w-full items-center gap-2 rounded-lg border px-2.5 py-1.5 text-[13px] font-medium"
    >
      <Plus aria-hidden="true" className="size-3.5 shrink-0" />
      <span className="flex-1 text-left">New run</span>
      <kbd
        aria-hidden="true"
        className="text-muted-foreground border-sidebar-border rounded border px-1 font-mono text-[11px]"
      >
        ⇧⌘O
      </kbd>
    </button>
  );
}
