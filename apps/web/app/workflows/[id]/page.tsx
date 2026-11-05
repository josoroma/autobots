import type { Metadata } from "next";

import { WorkflowEditor } from "@/components/workflow-editor";

export const metadata: Metadata = { title: "Workflow" };

export default async function WorkflowPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="max-w-4xl space-y-6">
      <h1 className="text-2xl font-semibold">Workflow</h1>
      <WorkflowEditor workflowId={id} />
    </div>
  );
}
