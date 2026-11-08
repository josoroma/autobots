import type { Metadata } from "next";
import { Suspense } from "react";

import { PageHeader } from "@/components/ui/page-header";
import { WorkflowsPanel } from "@/components/workflows-panel";

export const metadata: Metadata = { title: "Workflows" };

export default function WorkflowsPage() {
  return (
    <div className="@container max-w-6xl space-y-8">
      <PageHeader
        title="Workflows"
        description="Graphs of blocks, published as numbered versions. An execution runs one published version, and publishing never changes an earlier one."
      />
      <Suspense
        fallback={
          <p role="status" className="text-muted-foreground text-sm">
            Loading workflows.
          </p>
        }
      >
        <WorkflowsPanel />
      </Suspense>
    </div>
  );
}
