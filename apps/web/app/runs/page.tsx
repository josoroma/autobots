import type { Metadata } from "next";
import { Suspense } from "react";

import { RunList } from "@/components/run-list";

export const metadata: Metadata = { title: "Runs" };

export default function RunsPage() {
  return (
    <Suspense
      fallback={
        <p role="status" className="text-muted-foreground text-sm">
          Loading runs.
        </p>
      }
    >
      <RunList />
    </Suspense>
  );
}
