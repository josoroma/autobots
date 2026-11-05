import type { Metadata } from "next";

import { OperationsPanel } from "@/components/operations-panel";

export const metadata: Metadata = { title: "Operations" };

export default function OperationsPage() {
  return (
    <div className="max-w-3xl space-y-6">
      <h1 className="text-2xl font-semibold">Operations</h1>
      <OperationsPanel />
    </div>
  );
}
