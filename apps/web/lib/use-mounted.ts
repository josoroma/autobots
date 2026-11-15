import { useSyncExternalStore } from "react";

const subscribe = () => () => undefined;

/**
 * False on the server and while the page hydrates, true after. A control whose state depends on this
 * browser renders that state only then, so no hydration warning is hidden (DS-02, WSHL-11).
 */
export function useMounted(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => true,
    () => false,
  );
}
