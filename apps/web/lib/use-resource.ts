/**
 * One client read with explicit view states (XWEB-02, XERR-04, WRUN-16). It aborts a read that a
 * newer one replaces, shares identical GETs in flight through the read client, and keeps nothing
 * outside the component that asked. A read is a view of durable state: polling and Retry only read
 * again (PRD-Development-Harness DH-06). Reads are generated operations (R-48): pass
 * `readOf(operation, ...args)`, which may be built again on every render.
 */
import { useCallback, useEffect, useState } from "react";

import { keptRead, load, type Loaded, type Read } from "@/lib/load";

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
  /** The newest ready value for this read, kept through later failures, such as while reconnecting. */
  value: T | null;
  /** The current read, or a reload of it, hasn't settled yet. */
  pending: boolean;
  /** Counts settled reads, so a screen can reset what it derived from the previous one. */
  settled: number;
  /** When the shown read settled, in epoch milliseconds, or null before the first. */
  settledAt: number | null;
  /** Reads again. Nothing is sent while the read is null. */
  reload: () => void;
  /**
   * Forgets every read and reads again, so nothing read before is shown, such as results from an
   * earlier search when a palette opens again.
   */
  clear: () => void;
}

interface Settled<T> {
  source: Read<T>;
  request: number;
  loaded: Loaded<T>;
  failures: number;
  count: number;
  at: number;
  last: { source: Read<T>; value: T } | null;
}

/** The record of a read that settled, after `previous`. */
function settledAfter<T>(
  previous: Settled<T> | null,
  source: Read<T>,
  request: number,
  loaded: Loaded<T>,
): Settled<T> {
  return {
    source,
    request,
    loaded,
    failures:
      loaded.kind === "ready"
        ? 0
        : (previous?.source === source ? previous.failures : 0) + 1,
    count: (previous?.count ?? 0) + 1,
    at: Date.now(),
    last:
      loaded.kind === "ready"
        ? { source, value: loaded.value }
        : (previous?.last ?? null),
  };
}

/** What a screen sees of the newest settled read of `source`. */
function shown<T>(
  source: Read<T> | null,
  settled: Settled<T> | null,
): Pick<Resource<T>, "state" | "value" | "settled" | "settledAt"> {
  return {
    state:
      source === null
        ? { kind: "idle" }
        : settled === null
          ? { kind: "loading" }
          : settled.loaded,
    value:
      settled?.last != null && settled.last.source === source
        ? settled.last.value
        : null,
    settled: settled?.count ?? 0,
    settledAt: settled?.at ?? null,
  };
}

export function useResource<T>(
  wanted: Read<T> | null,
  options: ResourceOptions<T> = {},
): Resource<T> {
  const { delayMs = 0, poll } = options;
  // The effect below runs on `source`, never on `wanted`: a re-render that builds an equal read
  // keeps `source`, so only a changed operation or argument reads again.
  const [source, setSource] = useState(wanted);
  const next = keptRead(source, wanted);
  if (next !== source) setSource(next);
  const [request, setRequest] = useState(0);
  const [settled, setSettled] = useState<Settled<T> | null>(null);
  const reload = useCallback(() => setRequest((count) => count + 1), []);
  const clear = useCallback(() => {
    setSettled(null);
    setRequest((count) => count + 1);
  }, []);

  useEffect(() => {
    if (source === null) return;
    // A newer read replaces this one, so this one is aborted rather than left open (WRUN-16).
    const controller = new AbortController();
    const timer = setTimeout(() => {
      void load(source, { signal: controller.signal }).then((loaded) => {
        if (controller.signal.aborted) return;
        setSettled((previous) =>
          settledAfter(previous, source, request, loaded),
        );
      });
    }, delayMs);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [source, request, delayMs]);

  const current =
    settled !== null &&
    settled.source === source &&
    settled.request === request;
  useEffect(() => {
    if (poll === undefined || settled === null || !current) return;
    const wait = poll(settled.loaded, settled.failures);
    if (wait === null) return;
    const timer = setTimeout(() => setRequest((count) => count + 1), wait);
    return () => clearTimeout(timer);
  }, [poll, settled, current]);

  return {
    ...shown(source, settled),
    pending: source !== null && !current,
    reload,
    clear,
  };
}
