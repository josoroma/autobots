/**
 * The one read of a tab's requests (WTAP-04, R-27). A reply for another tab, or an older read, is
 * never listed, so waiting requests can't show under Decided. A failed reload of the same tab keeps
 * its counts, and a failed read shows why in place of the list, with Retry for an outage (WTAP-05).
 */
import {
  listApprovals,
  type ApprovalCounts,
  type ApprovalList,
  type ListApprovalsQuery,
} from "@autobots/api-client";
import { useEffect, useState } from "react";

import type { Tab } from "@/components/approvals/approval-tabs";
import { readOf } from "@/lib/load";
import { useResource, type ResourceState } from "@/lib/use-resource";

// The waiting tab sends no query, so its read is plain /api/v1/approvals.
const QUERIES: Readonly<Record<Tab, ListApprovalsQuery>> = {
  waiting: {},
  decided: { status: "decided" },
};

const LOADING = { kind: "loading" } as const;

export interface ApprovalListRead {
  /**
   * The tab's list while its newest read is ready. Null while it loads, while a Retry after a
   * failure is pending and once its read has failed, so a failed list never returns with live
   * buttons.
   */
  list: ApprovalList | null;
  /** The newest counts, from either tab, since they're the same for both; null before any. */
  counts: ApprovalCounts | null;
  /** What shows while there's no list: loading, also during a Retry, or why the read failed. */
  state: ResourceState<unknown>;
  pending: boolean;
  /** Epoch milliseconds that expiries are read against. */
  now: number;
  reload: () => void;
}

export function useApprovalList(tab: Tab): ApprovalListRead {
  const read = useResource(readOf(listApprovals, QUERIES[tab]));
  const [tick, setTick] = useState(() => Date.now());

  // Time left before an expiry is read against a clock that keeps moving, so a page left open never
  // says more time remains than does (Decision 0028 E5).
  useEffect(() => {
    if (tab !== "waiting") return;
    const timer = setInterval(() => setTick(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [tab]);

  const failed = !read.pending && read.state.kind !== "ready";
  const ready = read.state.kind === "ready" ? read.state.value : null;
  return {
    list: read.state.kind === "ready" ? read.value : null,
    counts: (read.value ?? ready)?.counts ?? null,
    state: failed ? read.state : LOADING,
    pending: read.pending,
    now: Math.max(tick, read.settledAt ?? 0),
    reload: read.reload,
  };
}
