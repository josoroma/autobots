/**
 * The Experts list's reads (XWEB-05, WBLD-12): the Experts, and the tool catalog their classes and
 * approval notes come from (PRD-Studio EX-02, EX-03). Each read has its own state; until the catalog
 * is read, no Expert is classified.
 */
import {
  listExperts,
  listTools,
  type ExpertList,
  type ExpertView,
  type ToolCatalog,
  type ToolDescriptor,
} from "@autobots/api-client";
import { useMemo } from "react";

import { classify, type ClassifiedExpert } from "@/lib/experts/card";
import { readOf } from "@/lib/load";
import { useResource, type Resource } from "@/lib/use-resource";

export interface ExpertListRead {
  list: Resource<ExpertList>;
  catalog: Resource<ToolCatalog>;
  /** The Experts, or null until they're read. */
  experts: readonly ExpertView[] | null;
  /** The catalog's tools by ID, or null until it's read. */
  tools: ReadonlyMap<string, ToolDescriptor> | null;
  classified: ClassifiedExpert[];
  /** When the list was read, so each card's last run is measured from then, not during render. */
  now: number;
}

export function useExpertList(): ExpertListRead {
  const list = useResource(readOf(listExperts));
  const catalog = useResource(readOf(listTools));
  const experts = list.value?.experts ?? null;
  const tools = useMemo(
    () =>
      catalog.value === null
        ? null
        : new Map(catalog.value.tools.map((tool) => [tool.tool_id, tool])),
    [catalog.value],
  );
  const classified = useMemo(
    () => classify(experts ?? [], tools),
    [experts, tools],
  );
  return {
    list,
    catalog,
    experts,
    tools,
    classified,
    now: list.settledAt ?? 0,
  };
}
