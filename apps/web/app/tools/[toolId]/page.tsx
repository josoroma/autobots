import type { Metadata } from "next";
import Link from "next/link";

import { ToolDetail } from "@/components/tool-catalog";

export const metadata: Metadata = { title: "Tool" };

export default async function ToolPage({
  params,
}: {
  params: Promise<{ toolId: string }>;
}) {
  const { toolId } = await params;
  return (
    <div className="max-w-4xl space-y-6">
      <p className="text-sm">
        <Link href="/tools" className="underline-offset-4 hover:underline">
          All tools
        </Link>
      </p>
      <h1 className="text-2xl font-semibold">Tool</h1>
      <ToolDetail toolId={toolId} />
    </div>
  );
}
