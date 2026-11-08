import type { Metadata } from "next";

import { ApprovalsPanel } from "@/components/approvals-panel";
import { PageHeader } from "@/components/ui/page-header";

export const metadata: Metadata = { title: "Approvals" };

export default function ApprovalsPage() {
  return (
    <div className="max-w-4xl space-y-6">
      <PageHeader title="Approvals" />
      <ApprovalsPanel />
    </div>
  );
}
