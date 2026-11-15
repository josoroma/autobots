/**
 * Arrived from New run or ⇧⌘O (PRD-Studio SH-02): focus the goal, then drop the marker from the
 * address.
 */
import { useEffect } from "react";

import { focusGoal, NEW_RUN_PARAM } from "@/components/new-run";

export function useNewRunFocus(): void {
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get(NEW_RUN_PARAM) !== "1") return;
    focusGoal();
    params.delete(NEW_RUN_PARAM);
    const rest = params.toString();
    window.history.replaceState(
      window.history.state,
      "",
      `${window.location.pathname}${rest === "" ? "" : `?${rest}`}`,
    );
  }, []);
}
