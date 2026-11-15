import type { Metadata } from "next";
import { Suspense } from "react";

import { ApprovalsPanel } from "@/components/approvals/approvals-panel";
import { PageHeader } from "@/components/ui/page-header";

export const metadata: Metadata = { title: "Approvals" };

export default function ApprovalsPage() {
  return (
    <div className="max-w-4xl space-y-6">
      <PageHeader title="Approvals" />
      {/* The panel reads its tab and selected request from the URL. */}
      <Suspense
        fallback={
          <p role="status" className="text-muted-foreground text-sm">
            Loading approvals.
          </p>
        }
      >
        <ApprovalsPanel />
      </Suspense>
    </div>
  );
}
