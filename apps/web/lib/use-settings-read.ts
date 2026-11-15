/**
 * A settings panel's one initial read, on `useResource` (WSYS-03, XDUP-18). A write's accepted
 * reply is shown until a read settles after it arrived, and a failed read shows why in its place,
 * with Retry for an outage. Nothing is kept outside the component that asked.
 */
import { useState } from "react";

import { shownValue, type Written } from "@/lib/settings-value";
import { useResource, type ResourceState } from "@/lib/use-resource";

export interface SettingsRead<T> {
  /** The newest value, or null while the first read is pending or once the newest has failed. */
  value: T | null;
  /** What shows while there's no value: loading, or why the read failed. */
  state: ResourceState<unknown>;
  pending: boolean;
  reload: () => void;
  /** Shows a write's reply as the value, stamped when it's called, until a later read settles. */
  adopt: (next: T) => void;
}

export function useSettingsRead<T>(
  path: string,
  parse: (value: unknown) => T,
): SettingsRead<T> {
  const read = useResource(path, parse);
  const [written, setWritten] = useState<Written<T> | null>(null);
  const failed = !read.pending && read.state.kind !== "ready";
  return {
    value: failed ? null : shownValue(read.value, read.settledAt, written),
    state: read.state,
    pending: read.pending,
    reload: read.reload,
    adopt: (next) => setWritten({ at: Date.now(), value: next }),
  };
}
