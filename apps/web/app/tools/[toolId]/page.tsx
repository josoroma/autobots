import { ArrowLeft } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { ToolDetail } from "@/components/tools/tool-detail";
import { PageHeader } from "@/components/ui/page-header";

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
        <Link
          href="/tools"
          className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 underline-offset-4 hover:underline"
        >
          <ArrowLeft aria-hidden="true" className="size-3.5" />
          All tools
        </Link>
      </p>
      <PageHeader title="Tool" />
      <ToolDetail toolId={toolId} />
    </div>
  );
}
