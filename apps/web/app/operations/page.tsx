import type { Metadata } from "next";

import { OperationsPanel } from "@/components/operations/operations-panel";
import { PageHeader } from "@/components/ui/page-header";

export const metadata: Metadata = { title: "Operations" };

export default function OperationsPage() {
  return (
    <div className="max-w-6xl space-y-6">
      <PageHeader title="Operations" />
      <OperationsPanel />
    </div>
  );
}
