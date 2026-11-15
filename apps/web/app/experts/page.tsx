import type { Metadata } from "next";
import { Suspense } from "react";

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
      {/* The panel reads its filters from the URL. */}
      <Suspense
        fallback={
          <p role="status" className="text-muted-foreground text-sm">
            Loading Experts.
          </p>
        }
      >
        <ExpertsPanel />
      </Suspense>
    </div>
  );
}
