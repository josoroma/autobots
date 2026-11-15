import type { Metadata } from "next";

import { ExpertsPanel } from "@/components/experts/experts-panel";
import { PageHeader } from "@/components/ui/page-header";

export const metadata: Metadata = { title: "Experts" };

export default function ExpertsPage() {
  return (
    <div className="@container max-w-6xl space-y-8">
      <PageHeader
        title="Experts"
        description="Specialists with their own purpose, instructions, granted tools and model. Open one to work with it directly, or include several in a coordinator session."
      />
      <ExpertsPanel />
    </div>
  );
}
