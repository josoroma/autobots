import type { Metadata } from "next";

import { RunInspectorView } from "@/components/run-inspector";

export const metadata: Metadata = { title: "Run inspector" };

export default async function RunInspectorPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <RunInspectorView runId={id} />;
}
