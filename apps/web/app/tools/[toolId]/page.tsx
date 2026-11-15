import { ArrowLeft } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { ToolDetailBody } from "@/components/tools/tool-detail-body";
import { ToolGrants } from "@/components/tools/tool-grants";
import { PageVersionSelect } from "@/components/tools/version-select";
import { LoadState, ServerLoadState } from "@/components/ui/load-state";
import { PageHeader } from "@/components/ui/page-header";
import { firstParam, type SearchParam } from "@/lib/list-filter";
import { readToolVersions } from "@/lib/server-api";

export const metadata: Metadata = { title: "Tool" };

const LOADING = { kind: "loading" } as const;

/** The version the URL's ?version= names, or the newest. */
async function Tool({
  toolId,
  version,
}: {
  toolId: string;
  version: string | null;
}) {
  const read = await readToolVersions(toolId);
  if (read.kind !== "ready")
    return (
      <ServerLoadState
        state={read}
        what="this tool"
        notFound="That tool isn't in the catalog."
      />
    );
  const versions = read.value.versions;
  const tool =
    versions.find((item) => String(item.version) === version) ??
    versions.at(-1);
  if (tool === undefined) return null;
  return (
    <ToolDetailBody
      tool={tool}
      version={
        <PageVersionSelect
          value={tool.version}
          versions={versions.map((item) => item.version)}
        />
      }
      grants={<ToolGrants toolId={tool.tool_id} />}
    />
  );
}

// PRD-Tool-Catalog TS-02: one tool's page, read and rendered on the server, streaming in below the
// title (R-67). The version control, Copy schema and who grants the tool are the parts that run in
// the browser.
export default async function ToolPage({
  params,
  searchParams,
}: {
  params: Promise<{ toolId: string }>;
  searchParams: Promise<Record<string, SearchParam>>;
}) {
  const { toolId } = await params;
  const version = firstParam((await searchParams).version);
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
      <Suspense fallback={<LoadState state={LOADING} what="this tool" />}>
        <Tool toolId={toolId} version={version} />
      </Suspense>
    </div>
  );
}
