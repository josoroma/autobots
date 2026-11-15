import type { Metadata } from "next";

import { RunWorkspaceView } from "@/components/runs/workspace/run-workspace";

export const metadata: Metadata = { title: "Run" };

export default async function RunPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <RunWorkspaceView runId={id} />;
}
