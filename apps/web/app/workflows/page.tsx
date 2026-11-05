import type { Metadata } from "next";

import { WorkflowsPanel } from "@/components/workflows-panel";

export const metadata: Metadata = { title: "Workflows" };

export default function WorkflowsPage() {
  return (
    <div className="max-w-3xl space-y-6">
      <h1 className="text-2xl font-semibold">Workflows</h1>
      <WorkflowsPanel />
    </div>
  );
}
