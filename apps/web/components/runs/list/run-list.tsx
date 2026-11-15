"use client";

import type { RunList as RunListView } from "@autobots/api-client";
import { useRouter } from "next/navigation";

import { RunListFilters } from "@/components/runs/list/run-filters";
import { RunRows } from "@/components/runs/list/run-rows";
import { useMoreRuns } from "@/components/runs/list/use-more-runs";
import { RunPanel } from "@/components/runs/panel/run-panel";
import { ServerLoadState } from "@/components/ui/load-state";
import type { Loaded } from "@/lib/load";
import {
  runFilterQuery,
  runFilterQueryForUrl,
  runFiltersFromQuery,
  type RunFilters,
} from "@/lib/runs/list";
import { useUrlDraft } from "@/lib/use-url-draft";
import { useUrlParams } from "@/lib/use-url-params";

/**
 * The runs list (PRD-Studio RN-01 to RN-04). The page reads its first page on the server for the
 * URL's filters (R-67). The status, search and model show what the person chose at once, and the
 * URL follows them together once they pause, built from those choices rather than from a URL whose
 * page is still on its way, so no choice undoes another. The selected run's panel is ?run=, which
 * changes in place, so choosing a run keeps the pages Load more added.
 */
export function RunList({
  first,
  filters,
}: {
  first: Loaded<RunListView>;
  filters: RunFilters;
}) {
  const router = useRouter();
  const url = useUrlParams();
  // RN-04: the selected run's panel, in the address so a reload keeps it open.
  const selected = url.get("run");
  const runs = useMoreRuns(
    first.kind === "ready" ? first.value : null,
    filters,
  );
  const chosen = useUrlDraft(
    runFilterQuery(filters),
    (query) => url.navigate(query, { run: selected }),
    { delayMs: 150, normalize: runFilterQueryForUrl },
  );
  const intended = runFiltersFromQuery(chosen.value);
  return (
    <>
      <RunListFilters
        filters={intended}
        list={runs.list}
        onChange={(patch) =>
          chosen.change(runFilterQuery({ ...intended, ...patch }, true))
        }
      />
      {first.kind !== "ready" ? (
        <ServerLoadState state={first} what="runs" />
      ) : runs.list === null ? null : (
        <RunRows
          list={runs.list}
          more={runs.more}
          selected={selected}
          onMore={() => void runs.loadMore()}
          onSelect={(runId) => url.replace({ run: runId })}
        />
      )}
      {selected === null ? null : (
        // A command changes the run, so the page reads its first page again on the server.
        <RunPanel
          key={selected}
          runId={selected}
          onChanged={() => router.refresh()}
        />
      )}
    </>
  );
}
