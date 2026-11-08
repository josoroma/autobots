import type { Metadata } from "next";

import { PageHeader } from "@/components/ui/page-header";
import { WorkflowMonitor } from "@/components/workflow-monitor";

export const metadata: Metadata = { title: "Execution" };

export default async function ExecutionPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="@container max-w-5xl space-y-8">
      <PageHeader title="Execution" />
      <WorkflowMonitor executionId={id} />
    </div>
  );
}
