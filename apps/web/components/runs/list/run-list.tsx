"use client";

import { useSearchParams } from "next/navigation";

import { RunListFilters } from "@/components/runs/list/run-filters";
import { RunRows } from "@/components/runs/list/run-rows";
import { useRunList } from "@/components/runs/list/use-run-list";
import { RunPanel } from "@/components/runs/panel/run-panel";
import { LoadState } from "@/components/ui/load-state";
import { PageHeader } from "@/components/ui/page-header";

export function RunList() {
  const runs = useRunList();
  // RN-04: the selected run's panel, in the address so a reload keeps it open.
  const selected = useSearchParams().get("run");
  return (
    <div className="max-w-6xl space-y-5">
      <PageHeader
        title="Runs"
        description="Every goal started on this Mac, from queued to finished. A finished run can't resume; start a similar one instead."
      />
      <RunListFilters
        filters={runs.filters}
        list={runs.list}
        onChange={runs.filter}
      />
      {runs.list === null ? (
        <LoadState
          state={runs.state}
          what="runs"
          onRetry={runs.reload}
          pending={runs.pending}
        />
      ) : (
        <RunRows
          list={runs.list}
          more={runs.more}
          selected={selected}
          onMore={() => void runs.loadMore()}
        />
      )}
      {selected === null ? null : (
        <RunPanel key={selected} runId={selected} onChanged={runs.reload} />
      )}
    </div>
  );
}
