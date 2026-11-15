"use client";

import { getToolGrants, getToolVersions } from "@autobots/api-client";
import { useState } from "react";

import { GrantedTo } from "@/components/tools/granted-to";
import { ToolDetailBody } from "@/components/tools/tool-detail-body";
import { VersionSelect } from "@/components/tools/version-select";
import { LoadState } from "@/components/ui/load-state";
import { readOf } from "@/lib/load";
import { useResource } from "@/lib/use-resource";

/**
 * One tool's detail in the Tools page's dialog (Decision 0026 G2), which opens over a list already in
 * the browser, so it reads there. Any registered version can be shown; the tool's own page reads on
 * the server instead (app/tools/[toolId]/page.tsx).
 */
export function ToolDetail({ toolId }: { toolId: string }) {
  const { state, pending, reload } = useResource(
    readOf(getToolVersions, toolId),
  );
  // Who grants the tool needs only its ID, so it's read alongside its versions, not after them.
  const grants = useResource(readOf(getToolGrants, toolId));
  const [chosen, setChosen] = useState<number | null>(null);
  if (state.kind !== "ready") {
    return (
      <LoadState
        state={state}
        what="this tool"
        notFound="That tool isn't in the catalog."
        onRetry={reload}
        pending={pending}
      />
    );
  }
  const versions = state.value.versions;
  const newest = versions.at(-1);
  if (newest === undefined) return null;
  const tool = versions.find((item) => item.version === chosen) ?? newest;
  return (
    <ToolDetailBody
      tool={tool}
      version={
        <VersionSelect
          value={tool.version}
          versions={versions.map((item) => item.version)}
          onChoose={setChosen}
        />
      }
      grants={<GrantedTo toolId={tool.tool_id} grants={grants} />}
    />
  );
}
