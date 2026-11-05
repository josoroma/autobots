import type { Metadata } from "next";

import { SessionPanel } from "@/components/session-panel";

export const metadata: Metadata = { title: "Session" };

export default async function SessionPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="max-w-3xl space-y-6">
      <h1 className="text-2xl font-semibold">Session</h1>
      <SessionPanel sessionId={id} />
    </div>
  );
}
