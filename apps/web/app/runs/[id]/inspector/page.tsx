import type { Metadata } from "next";
import { Suspense } from "react";

import {
  InspectorLead,
  RunInspectorView,
} from "@/components/runs/inspector/run-inspector";
import { LoadState, ServerLoadState } from "@/components/ui/load-state";
import { PageHeader } from "@/components/ui/page-header";
import { RUN_NOT_FOUND } from "@/lib/runs/workspace-load";
import { readRunInspector } from "@/lib/server-api";

export const metadata: Metadata = { title: "Run inspector" };

const LOADING = { kind: "loading" } as const;

/** The run's goal under the title, once the read has it. The body below shares the same read. */
async function Lead({ runId }: { runId: string }) {
  const read = await readRunInspector(runId);
  return read.kind === "ready" ? (
    <InspectorLead runId={runId} view={read.value} />
  ) : null;
}

// A refusal, a missing run and a mismatch each say so, and only an outage offers Retry (WRUN-02).
async function Inspector({ runId }: { runId: string }) {
  const read = await readRunInspector(runId);
  return read.kind === "ready" ? (
    <RunInspectorView view={read.value} />
  ) : (
    <ServerLoadState state={read} what="this run" notFound={RUN_NOT_FOUND} />
  );
}

// The page reads the run on the server and owns its title and width in every state (XWEB-19). The
// read streams in below the title, so a slow API never holds the page back.
export default async function RunInspectorPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <PageHeader
        title="Run inspector"
        description={
          <Suspense fallback={null}>
            <Lead runId={id} />
          </Suspense>
        }
      />
      <Suspense fallback={<LoadState state={LOADING} what="this run" />}>
        <Inspector runId={id} />
      </Suspense>
    </div>
  );
}
