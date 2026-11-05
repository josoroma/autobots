import type { Metadata } from "next";

import { ApprovalsPanel } from "@/components/approvals-panel";

export const metadata: Metadata = { title: "Approvals" };

export default function ApprovalsPage() {
  return (
    <div className="max-w-3xl space-y-6">
      <h1 className="text-2xl font-semibold">Approvals</h1>
      <ApprovalsPanel />
    </div>
  );
}
