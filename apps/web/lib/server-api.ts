import "server-only";

import {
  getRetentionSummary,
  getRunInspector,
  getToolVersions,
  getWorkSession,
  listApprovals,
  listRuns,
  type ApprovalList,
  type ModelProfileId,
  type RetentionSummary,
  type RunInspector,
  type RunList,
  type SessionView,
  type ToolVersions,
} from "@autobots/api-client";
import type { ClientOptions } from "@autobots/api-client/runtime";
import { unstable_rethrow } from "next/navigation";
import { cache } from "react";

import { loadFailure, worstFailure, type Loaded } from "@/lib/load-failure";
import { runListQuery, type RunGroup } from "@/lib/runs/list";
import { logFailure } from "@/lib/server-log";
import { memberClient } from "@/lib/service-status";

/**
 * The reads a page makes on the server (R-67, XWEB-14, WCMP-07, WRUN-14): the generated operations,
 * called with the same per-request session token and chosen workspace that the BFF sends
 * (lib/bff.ts), so the API checks membership on each as it does for the browser. Each result is a
 * `Loaded`, classified as the browser's reads are (lib/load-failure.ts), so a page shows the same
 * words and hooks. React's `cache()` keeps a result for one server request only; nothing here is
 * shared between requests or people (PRD-Development-Harness DH-06).
 *
 * These reads don't run the BFF's request guard (lib/request-guard.ts): its host check
 * (`forbidden_host`) and its `Sec-Fetch-Site` check. That guard stops another site from using the
 * person's cookies to call the JSON routes. A page read sends only the session and workspace
 * cookies its own request carried, and both are set host-only and SameSite=Strict by
 * `cookieOptions` (lib/bff-policy.ts). A page reached through another host name, as DNS
 * rebinding would reach it, or from another site, arrives without them and reads as signed out.
 * The page itself goes only to the browser that asked for it, which no other origin can read.
 */

// A page's read gives up when the BFF's forward does, so a slow read reads the same whichever asked.
const PAGE_TIMEOUT_MS = 30_000;

/** How many recent runs Home shows (PRD-Studio HM-04), and so asks the API for. */
export const RECENT_RUNS = 5;

/**
 * Next's own control flow is rethrown. A refusal is for the person to read, and an outage's or a
 * mismatch's cause stays in the server's log (WSHL-02).
 */
async function pageRead<T>(
  operation: string,
  call: (options: ClientOptions) => Promise<T>,
): Promise<Loaded<T>> {
  try {
    const options = await memberClient(true, PAGE_TIMEOUT_MS);
    if (options === null) return { kind: "signed_out" };
    return { kind: "ready", value: await call(options) };
  } catch (error) {
    unstable_rethrow(error);
    const failure = loadFailure(error);
    if (failure.kind === "unavailable" || failure.kind === "out_of_date")
      logFailure(operation, error);
    return failure;
  }
}

/** US-11.5: one run's model calls, tool attempts, evidence and checkpoints, sanitized by the API. */
export const readRunInspector = cache(
  (runId: string): Promise<Loaded<RunInspector>> =>
    pageRead("runs.inspector.read", (options) =>
      getRunInspector(options, runId),
    ),
);

/** PRD-Studio RN-01, RN-02: the first page of runs for the URL's filters. */
export const readRunList = cache(
  (
    group: RunGroup,
    query: string,
    profile: ModelProfileId | "",
  ): Promise<Loaded<RunList>> =>
    pageRead("runs.list", (options) =>
      listRuns(options, runListQuery({ group, query, profile }, null)),
    ),
);

export interface HomeActivityRead {
  approvals: ApprovalList;
  waiting: RunList;
  recent: RunList;
  /** When the reads settled, which relative times are measured from. */
  readAt: number;
}

/**
 * PRD-Studio HM-04, Decision 0022 D9: pending approvals, the runs that need the person and the five
 * newest runs, as one result, since either section alone would mislead.
 */
export const readHomeActivity = cache(
  async (): Promise<Loaded<HomeActivityRead>> => {
    const [approvals, waiting, recent] = await Promise.all([
      pageRead("approvals.list", (options) => listApprovals(options)),
      pageRead("runs.list", (options) =>
        listRuns(options, { group: "needs_you" }),
      ),
      pageRead("runs.list", (options) =>
        listRuns(options, { limit: RECENT_RUNS }),
      ),
    ]);
    if (
      approvals.kind === "ready" &&
      waiting.kind === "ready" &&
      recent.kind === "ready"
    ) {
      return {
        kind: "ready",
        value: {
          approvals: approvals.value,
          waiting: waiting.value,
          recent: recent.value,
          readAt: Date.now(),
        },
      };
    }
    return (
      worstFailure([approvals, waiting, recent]) ?? {
        kind: "unavailable",
        status: null,
      }
    );
  },
);

/** PRD-Studio SE-06: what this workspace keeps, for any member. */
export const readRetentionSummary = cache(
  (): Promise<Loaded<RetentionSummary>> =>
    pageRead("retention.read", (options) => getRetentionSummary(options)),
);

/** US-5.1: a direct or coordinator session and the Experts it can route to. */
export const readWorkSession = cache(
  (sessionId: string): Promise<Loaded<SessionView>> =>
    pageRead("sessions.read", (options) => getWorkSession(options, sessionId)),
);

/** PRD-Tool-Catalog TS-02: every registered version of one tool. */
export const readToolVersions = cache(
  (toolId: string): Promise<Loaded<ToolVersions>> =>
    pageRead("tools.versions.read", (options) =>
      getToolVersions(options, toolId),
    ),
);
