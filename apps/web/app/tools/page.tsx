import type { Metadata } from "next";
import { Suspense } from "react";

import { ToolCatalogPanel } from "@/components/tool-catalog";

export const metadata: Metadata = { title: "Tools" };

export default function ToolsPage() {
  return (
    <div className="max-w-4xl space-y-6">
      <h1 className="text-2xl font-semibold">Tools</h1>
      <p className="text-muted-foreground text-sm">
        Every tool this install knows, granted or not. Seeing a tool here
        doesn&apos;t let anything call it: an Expert, goal or workflow has to
        grant it.
      </p>
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
