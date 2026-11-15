import type { Metadata } from "next";
import { Suspense } from "react";

import { RunList } from "@/components/runs/list/run-list";
import { PageHeader } from "@/components/ui/page-header";
import type { SearchParam } from "@/lib/list-filter";
import { runFiltersFrom, type RunFilters } from "@/lib/runs/list";
import { readRunList } from "@/lib/server-api";

export const metadata: Metadata = { title: "Runs" };

// PRD-Studio RN-01, RN-02: the first page is read on the server for the URL's filters, so a reload,
// Back and a shared link keep them (XWEB-13, R-67). The page owns the title and width (XWEB-19).
async function FirstPage({ filters }: { filters: RunFilters }) {
  const first = await readRunList(
    filters.group,
    filters.query,
    filters.profile,
  );
  return <RunList first={first} filters={filters} />;
}

export default async function RunsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, SearchParam>>;
}) {
  const filters = runFiltersFrom(await searchParams);
  return (
    <div className="max-w-6xl space-y-5">
      <PageHeader
        title="Runs"
        description="Every goal started on this Mac, from queued to finished. A finished run can't resume; start a similar one instead."
      />
      <Suspense
        fallback={
          <p
            role="status"
            data-state="loading"
            className="text-muted-foreground text-sm"
          >
            Loading runs.
          </p>
        }
      >
        <FirstPage filters={filters} />
      </Suspense>
    </div>
  );
}
