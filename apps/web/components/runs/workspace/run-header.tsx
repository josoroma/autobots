import type { RunStatus } from "@autobots/api-client";
import { ScanSearch } from "lucide-react";
import Link from "next/link";
import { memo } from "react";

import { RunStateBadge } from "@/components/runs/run-state";
import { buttonVariants } from "@/components/ui/button";

export const RunHeader = memo(function RunHeader({
  runId,
  status,
}: {
  runId: string;
  status: RunStatus;
}) {
  return (
    <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="flex min-w-0 flex-wrap items-center gap-3">
        <h1 className="text-[32px] leading-tight">Run</h1>
        <RunStateBadge status={status} />
      </div>
      <p className="text-sm">
        <Link
          href={`/runs/${runId}/inspector`}
          className={buttonVariants({ variant: "outline", size: "sm" })}
        >
          <ScanSearch aria-hidden="true" />
          Inspect this run
        </Link>
      </p>
    </header>
  );
});
