import type { Metadata } from "next";
import { Suspense } from "react";

import { ToolCatalogPanel } from "@/components/tools/tool-catalog-panel";
import { PageHeader } from "@/components/ui/page-header";

export const metadata: Metadata = { title: "Tools" };

export default function ToolsPage() {
  return (
    <div className="max-w-5xl space-y-6">
      <PageHeader
        title="Tools"
        description={
          <>
            Every tool this install knows, granted or not. Seeing a tool here
            doesn&apos;t let anything call it: an Expert, goal or workflow has
            to grant it.
          </>
        }
      />
      <Suspense
        fallback={
          <p role="status" className="text-sm">
            Loading the tool catalog.
          </p>
        }
      >
        <ToolCatalogPanel />
      </Suspense>
    </div>
  );
}
