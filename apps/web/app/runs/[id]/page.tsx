import type { Metadata } from "next";

import {
  InspectRunLink,
  RunStatusBadge,
  RunStatusProvider,
} from "@/components/runs/workspace/run-heading";
import { RunWorkspaceView } from "@/components/runs/workspace/run-workspace";
import { PageHeader } from "@/components/ui/page-header";

export const metadata: Metadata = { title: "Run" };

// The page owns the title and width in every state (XWEB-19). The status badge, which is hidden from
// assistive technology as the status sentence says the same, and the inspector's link follow the
// snapshot the workspace reads live.
export default async function RunPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <RunStatusProvider>
      <div className="mx-auto max-w-6xl space-y-6">
        <PageHeader
          title={
            <span className="inline-flex flex-wrap items-center gap-3">
              Run
              <RunStatusBadge />
            </span>
          }
          actions={<InspectRunLink runId={id} />}
        />
        <RunWorkspaceView runId={id} />
      </div>
    </RunStatusProvider>
  );
}
