import type { Metadata } from "next";

import { DataSummary } from "@/components/data-summary";
import { PageHeader } from "@/components/ui/page-header";

export const metadata: Metadata = { title: "Data on this Mac" };

export default function DataPage() {
  return (
    <div className="max-w-3xl space-y-6">
      <PageHeader title="Data on this Mac" />
      <DataSummary />
    </div>
  );
}
