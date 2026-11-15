import type { Metadata } from "next";

import { ExpertEditor } from "@/components/expert-editor/expert-editor";
import { PageHeader } from "@/components/ui/page-header";

export const metadata: Metadata = { title: "Expert" };

export default async function ExpertPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="@container max-w-6xl space-y-8">
      <PageHeader title="Expert" />
      <ExpertEditor expertId={id} />
    </div>
  );
}
