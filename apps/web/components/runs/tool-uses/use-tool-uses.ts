import { parseToolUseList, type ToolUseView } from "@autobots/api-client";
import { useCallback, useEffect, useState } from "react";

import { loadJson, type LoadFailure } from "@/lib/load";

export interface ToolUses {
  uses: ToolUseView[] | null;
  /** Why the newest read failed. Uses already shown stay shown. */
  failure: LoadFailure | null;
  pending: boolean;
  reload: () => void;
}

/**
 * Every page of a run's uses, read again whenever `version` changes. A caller passes a value that
 * changes only when the uses may have, so a poll that finds nothing new reads nothing (WBLD-08).
 */
export function useToolUses(runId: string, version: number | string): ToolUses {
  const [request, setRequest] = useState(0);
  const key = `${request}|${runId}|${version}`;
  const [state, setState] = useState<{
    key: string;
    uses: ToolUseView[] | null;
    failure: LoadFailure | null;
  }>({ key: "", uses: null, failure: null });
  useEffect(() => {
    // A newer read replaces this one, so this one is aborted rather than left open.
    const controller = new AbortController();
    const load = async (): Promise<void> => {
      const all: ToolUseView[] = [];
      let after = 0;
      for (;;) {
        const page = await loadJson(
          `/api/v1/runs/${encodeURIComponent(runId)}/tool-uses?after=${after}&limit=200`,
          parseToolUseList,
          { signal: controller.signal },
        );
        if (controller.signal.aborted) return;
        if (page.kind !== "ready") {
          setState((current) => ({ ...current, key, failure: page }));
          return;
        }
        all.push(...page.value.uses);
        if (page.value.next_cursor === null) break;
        after = page.value.next_cursor;
      }
      setState({ key, uses: all, failure: null });
    };
    void load();
    return () => controller.abort();
  }, [runId, key]);
  const reload = useCallback(() => setRequest((count) => count + 1), []);
  return {
    uses: state.uses,
    failure: state.failure,
    pending: state.key !== key,
    reload,
  };
}
