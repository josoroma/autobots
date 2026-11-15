"use client";

import { getToolGrants } from "@autobots/api-client";

import { GrantedTo } from "@/components/tools/granted-to";
import { readOf } from "@/lib/load";
import { useResource } from "@/lib/use-resource";

/** PRD-Studio TL-02: who grants the tool, read in the browser beside the page's own read. */
export function ToolGrants({ toolId }: { toolId: string }) {
  const grants = useResource(readOf(getToolGrants, toolId));
  return <GrantedTo toolId={toolId} grants={grants} />;
}
