import type { Metadata } from "next";

import { ExpertsPanel } from "@/components/experts-panel";

export const metadata: Metadata = { title: "Experts" };

export default function ExpertsPage() {
  return (
    <div className="max-w-3xl space-y-6">
      <h1 className="text-2xl font-semibold">Experts</h1>
      <ExpertsPanel />
    </div>
  );
}
