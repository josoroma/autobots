import type { Metadata } from "next";

import { PageHeader } from "@/components/ui/page-header";
import { WorkflowEditor } from "@/components/workflow-editor";

export const metadata: Metadata = { title: "Workflow" };

export default async function WorkflowPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="@container max-w-6xl space-y-8">
      <PageHeader title="Workflow" />
      <WorkflowEditor workflowId={id} />
    </div>
  );
}
