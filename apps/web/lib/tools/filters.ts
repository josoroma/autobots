/**
 * The Tools page's filters (WTAP-08). They live in the URL, so a view can be linked
 * (PRD-Tool-Catalog TS-01), and the shown tools are grouped once, in the catalog's order. Pure and
 * JSX-free, so `node --test` covers it.
 */
import type { ToolDescriptor } from "@autobots/api-client";

import { matchesSearch, searchNeedle } from "../list-filter.ts";

/** What the filters read from a tool. */
export type FilterTool = Pick<
  ToolDescriptor,
  "tool_id" | "group" | "title" | "description" | "availability" | "provider"
>;

/** Each filter's value from the URL, empty for none, and the search as typed. */
export interface ToolFilters {
  group: string;
  availability: string;
  provider: string;
  search: string;
}

export function readToolFilters(params: {
  get: (name: string) => string | null;
}): ToolFilters {
  return {
    group: params.get("group") ?? "",
    availability: params.get("availability") ?? "",
    provider: params.get("provider") ?? "",
    search: params.get("q") ?? "",
  };
}

/** The tools every filter allows; the search matches a tool's title, ID or description. */
export function filterTools<T extends FilterTool>(
  tools: readonly T[],
  filters: ToolFilters,
): T[] {
  const needle = searchNeedle(filters.search);
  return tools.filter(
    (tool) =>
      (filters.group === "" || tool.group === filters.group) &&
      (filters.availability === "" ||
        tool.availability === filters.availability) &&
      (filters.provider === "" || tool.provider === filters.provider) &&
      matchesSearch(
        `${tool.title} ${tool.tool_id} ${tool.description}`,
        needle,
      ),
  );
}

/** Each group holding a shown tool, in the catalog's order, with its shown tools. */
export function groupTools<
  G extends { group: string },
  T extends { group: string },
>(groups: readonly G[], tools: readonly T[]): { group: G; tools: T[] }[] {
  const byGroup = new Map<string, T[]>();
  for (const tool of tools) {
    byGroup.set(tool.group, [...(byGroup.get(tool.group) ?? []), tool]);
  }
  return groups.flatMap((group) => {
    const inGroup = byGroup.get(group.group);
    return inGroup === undefined ? [] : [{ group, tools: inGroup }];
  });
}

/** Each provider once, in the order the catalog first lists it. */
export function providersOf<T extends Pick<ToolDescriptor, "provider">>(
  tools: readonly T[],
): T["provider"][] {
  return [...new Set(tools.map((tool) => tool.provider))];
}
