import type { Metadata } from "next";

import { WorkflowMonitor } from "@/components/workflow-monitor";

export const metadata: Metadata = { title: "Execution" };

export default async function ExecutionPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="max-w-4xl space-y-6">
      <h1 className="text-2xl font-semibold">Execution</h1>
      <WorkflowMonitor executionId={id} />
    </div>
  );
}
