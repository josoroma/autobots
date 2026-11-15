/**
 * A page-wide keyboard shortcut (WCMP-10). It never acts while focus is in a text field
 * (PRD-Studio SH-02, Decision 0022 D3). Pass a `match` defined outside the component and a stable
 * `handler`, so renders don't re-register it.
 */
import { useEffect } from "react";

import { typing, type KeyPress } from "@/lib/keyboard";

export function useShortcut(
  match: (event: KeyPress) => boolean,
  handler: () => void,
): void {
  useEffect(() => {
    function onKey(event: KeyboardEvent): void {
      if (!match(event) || typing(event.target)) return;
      event.preventDefault();
      handler();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [match, handler]);
}
