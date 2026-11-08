import type { Metadata } from "next";

import { SessionPanel } from "@/components/session-panel";
import { PageHeader } from "@/components/ui/page-header";

export const metadata: Metadata = { title: "Session" };

export default async function SessionPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="@container max-w-4xl space-y-8">
      <PageHeader title="Session" />
      <SessionPanel sessionId={id} />
    </div>
  );
}
