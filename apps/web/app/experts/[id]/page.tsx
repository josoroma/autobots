import type { Metadata } from "next";

import { ExpertEditor } from "@/components/expert-editor";

export const metadata: Metadata = { title: "Expert" };

export default async function ExpertPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="max-w-3xl space-y-6">
      <h1 className="text-2xl font-semibold">Expert</h1>
      <ExpertEditor expertId={id} />
    </div>
  );
}
