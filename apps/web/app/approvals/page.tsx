import type { Metadata } from "next";

import { ApprovalsPanel } from "@/components/approvals/approvals-panel";
import { PageHeader } from "@/components/ui/page-header";

export const metadata: Metadata = { title: "Approvals" };

export default async function ApprovalsPage({
  searchParams,
}: {
  searchParams: Promise<{ approval?: string | string[] }>;
}) {
  const { approval } = await searchParams;
  return (
    <div className="max-w-4xl space-y-6">
      <PageHeader title="Approvals" />
      <ApprovalsPanel
        initial={typeof approval === "string" ? approval : null}
      />
    </div>
  );
}
