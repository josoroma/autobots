import type { Metadata } from "next";
import { Suspense } from "react";

import { DataSummary } from "@/components/data-summary";
import { LoadState, ServerLoadState } from "@/components/ui/load-state";
import { PageHeader } from "@/components/ui/page-header";
import { readRetentionSummary } from "@/lib/server-api";

export const metadata: Metadata = { title: "Data on this Mac" };

const LOADING = { kind: "loading" } as const;

async function Summary() {
  const read = await readRetentionSummary();
  return read.kind === "ready" ? (
    <DataSummary summary={read.value} />
  ) : (
    <ServerLoadState state={read} what="the retention summary" />
  );
}

// The summary is read on the server and streams in below the title (R-67).
export default function DataPage() {
  return (
    <div className="max-w-3xl space-y-6">
      <PageHeader title="Data on this Mac" />
      <Suspense
        fallback={<LoadState state={LOADING} what="the retention summary" />}
      >
        <Summary />
      </Suspense>
    </div>
  );
}
