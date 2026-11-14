/**
 * One client read with explicit view states (XWEB-02, XERR-04, WRUN-16). It aborts a read that a
 * newer one replaces, shares identical GETs in flight through `loadJson`, and keeps nothing outside
 * the component that asked. A read is a view of durable state: polling and Retry only read again
 * (PRD-Development-Harness DH-06).
 */
import { useCallback, useEffect, useState } from "react";

import { loadJson, type Loaded } from "@/lib/load";

/** `idle` while there is nothing to read, such as an empty search. */
export type ResourceState<T> =
  { kind: "idle" } | { kind: "loading" } | Loaded<T>;

export interface ResourceOptions<T> {
  /** Waits this long before each read, so typing in a filter sends one request. */
  delayMs?: number;
  /**
   * After each settled read, the delay before reading again, or null to stop. `failures` counts
   * failed reads in a row. Pass a function defined outside the component, so renders don't reset it.
   */
  poll?: (loaded: Loaded<T>, failures: number) => number | null;
}

export interface Resource<T> {
  /** The newest settled read, or loading before the first. It stays shown while the next is pending. */
  state: ResourceState<T>;
  /** The newest ready value for this path, kept through later failures, such as while reconnecting. */
  value: T | null;
  /** A read for the current path, or for a reload, hasn't settled yet. */
  pending: boolean;
  /** Counts settled reads, so a screen can reset what it derived from the previous one. */
  settled: number;
  /** When the shown read settled, in epoch milliseconds, or null before the first. */
  settledAt: number | null;
  /** Reads again. Nothing is sent while the path is null. */
  reload: () => void;
  /**
   * Forgets every read and reads again, so nothing read before is shown, such as results from an
   * earlier search when a palette opens again.
   */
  clear: () => void;
}

interface Settled<T> {
  path: string;
  request: number;
  loaded: Loaded<T>;
  failures: number;
  count: number;
  at: number;
  last: { path: string; value: T } | null;
}

export function useResource<T>(
  path: string | null,
  parse: (value: unknown) => T,
  options: ResourceOptions<T> = {},
): Resource<T> {
  const { delayMs = 0, poll } = options;
  const [request, setRequest] = useState(0);
  const [settled, setSettled] = useState<Settled<T> | null>(null);
  const reload = useCallback(() => setRequest((count) => count + 1), []);
  const clear = useCallback(() => {
    setSettled(null);
    setRequest((count) => count + 1);
  }, []);

  useEffect(() => {
    if (path === null) return;
    // A newer read replaces this one, so this one is aborted rather than left open (WRUN-16).
    const controller = new AbortController();
    const timer = setTimeout(() => {
      void loadJson(path, parse, { signal: controller.signal }).then(
        (loaded) => {
          if (controller.signal.aborted) return;
          setSettled((previous) => ({
            path,
            request,
            loaded,
            failures:
              loaded.kind === "ready"
                ? 0
                : (previous?.path === path ? previous.failures : 0) + 1,
            count: (previous?.count ?? 0) + 1,
            at: Date.now(),
            last:
              loaded.kind === "ready"
                ? { path, value: loaded.value }
                : (previous?.last ?? null),
          }));
        },
      );
    }, delayMs);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [path, parse, request, delayMs]);

  const current =
    settled !== null && settled.path === path && settled.request === request;
  useEffect(() => {
    if (poll === undefined || settled === null || !current) return;
    const wait = poll(settled.loaded, settled.failures);
    if (wait === null) return;
    const timer = setTimeout(() => setRequest((count) => count + 1), wait);
    return () => clearTimeout(timer);
  }, [poll, settled, current]);

  return {
    state:
      path === null
        ? { kind: "idle" }
        : settled === null
          ? { kind: "loading" }
          : settled.loaded,
    value:
      settled?.last != null && settled.last.path === path
        ? settled.last.value
        : null,
    pending: path !== null && !current,
    settled: settled?.count ?? 0,
    settledAt: settled?.at ?? null,
    reload,
    clear,
  };
}
