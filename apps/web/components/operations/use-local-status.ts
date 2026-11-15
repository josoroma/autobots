/**
 * The one read of Operations' local status (WSYS-03, R-27). It reads again on Check again and after
 * a retention save, and a reply that arrives late never replaces a newer one (WTAP-04). The status
 * stays shown while a newer read is pending; a failed read shows why in its place.
 */
import { getLocalStatus, type LocalStatus } from "@autobots/api-client";

import { readOf } from "@/lib/load";
import { useResource, type ResourceState } from "@/lib/use-resource";

export interface LocalStatusRead {
  /** The newest status, or null while the first read is pending or once the newest has failed. */
  status: LocalStatus | null;
  /** What shows while there's no status: loading, or why the read failed. */
  state: ResourceState<unknown>;
  /** The newest read was refused as the owner's (PRD-Studio OP-01). */
  denied: boolean;
  pending: boolean;
  /** Counts settled reads, so the retention form shows each newer read's windows. */
  settled: number;
  reload: () => void;
}

export function useLocalStatus(): LocalStatusRead {
  const read = useResource(readOf(getLocalStatus));
  const failed = !read.pending && read.state.kind !== "ready";
  return {
    status: failed ? null : read.value,
    state: read.state,
    denied: failed && read.state.kind === "denied",
    pending: read.pending,
    settled: read.settled,
    reload: read.reload,
  };
}
