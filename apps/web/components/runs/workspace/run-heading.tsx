"use client";

import type { RunStatus } from "@autobots/api-client";
import { ScanSearch } from "lucide-react";
import Link from "next/link";
import { createContext, type ReactNode, use, useEffect, useState } from "react";

import { RunStateBadge } from "@/components/runs/run-state";
import { buttonVariants } from "@/components/ui/button";

// The run page owns its title and width (XWEB-19); the live parts of its header, the status badge
// and the way to the inspector, follow the snapshot the workspace below it reads in the browser.

const StatusContext = createContext<RunStatus | null>(null);
const PublishContext = createContext<(status: RunStatus | null) => void>(
  () => undefined,
);

/** Holds the run's status for the page's header, from the workspace's newest snapshot. */
export function RunStatusProvider({ children }: { children: ReactNode }) {
  const [status, publish] = useState<RunStatus | null>(null);
  return (
    <PublishContext value={publish}>
      <StatusContext value={status}>{children}</StatusContext>
    </PublishContext>
  );
}

/** The workspace reports its run's status, or null while it has none. */
export function usePublishRunStatus(status: RunStatus | null): void {
  const publish = use(PublishContext);
  useEffect(() => {
    publish(status);
    return () => publish(null);
  }, [publish, status]);
}

/** The run's status beside the page's title, once a snapshot has been read. */
export function RunStatusBadge() {
  const status = use(StatusContext);
  return status === null ? null : <RunStateBadge status={status} />;
}

/** The way to the inspector, once a snapshot has been read. */
export function InspectRunLink({ runId }: { runId: string }) {
  const status = use(StatusContext);
  if (status === null) return null;
  return (
    <Link
      href={`/runs/${runId}/inspector`}
      className={buttonVariants({ variant: "outline", size: "sm" })}
    >
      <ScanSearch aria-hidden="true" />
      Inspect this run
    </Link>
  );
}
