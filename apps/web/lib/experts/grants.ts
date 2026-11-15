/**
 * What an Expert may be granted and what a save records (WBLD-10): tools from the same catalog the
 * Tools page shows (PRD-Tool-Catalog TC-06, TS-04), whole groups, and the explicit list a version
 * stores, since a stored version names its tools and doesn't follow a group later. Pure and
 * JSX-free, so `node --test` covers it.
 */
import type { ToolDescriptor, ToolGroupDescriptor } from "@autobots/api-client";

import {
  AVAILABILITY_LABEL,
  repairText,
  type ToolState,
} from "../tools/text.ts";

/** What the grant rules read from a tool. */
export type GrantTool = Pick<
  ToolDescriptor,
  "tool_id" | "group" | "title" | "approval" | "grantable_to"
> &
  ToolState;

/** What the grant rules read from the catalog. */
export interface GrantCatalog<T extends GrantTool> {
  groups: readonly Pick<ToolGroupDescriptor, "group" | "title">[];
  tools: readonly T[];
}

/** A draft's grants: the tools it names and the groups it grants whole. */
export interface Grants {
  tools: readonly string[];
  groups: readonly string[];
}

/** One group an Expert may be granted whole, with its grantable tools. */
export interface GrantGroup<T extends GrantTool> {
  group: string;
  title: string;
  tools: readonly T[];
  /** It holds an unavailable tool, so it can be unchecked but not checked. */
  blocked: boolean;
}

/** The tools an Expert may be granted, or none before the catalog is read. */
export function grantable<T extends GrantTool>(
  catalog: GrantCatalog<T> | null,
): T[] {
  return (catalog?.tools ?? []).filter((tool) =>
    tool.grantable_to.includes("expert"),
  );
}

/** Each catalog group holding a tool an Expert may be granted, read once, in the catalog's order. */
export function grantGroups<T extends GrantTool>(
  catalog: GrantCatalog<T>,
): GrantGroup<T>[] {
  const offered = grantable(catalog);
  return catalog.groups.flatMap((group) => {
    const tools = offered.filter((tool) => tool.group === group.group);
    if (tools.length === 0) return [];
    return [
      {
        group: group.group,
        title: group.title,
        tools,
        blocked: tools.some((tool) => tool.availability !== "available"),
      },
    ];
  });
}

/** A group checkbox's name, which says how many tools it grants and whether one is unavailable. */
export function groupGrantLabel(group: GrantGroup<GrantTool>): string {
  const count = group.tools.length;
  return `${group.title} group (${count} ${count === 1 ? "tool" : "tools"})${
    group.blocked ? ", includes an unavailable tool" : ""
  }`;
}

/** A blocked group can be unchecked, never checked. */
export function groupLocked(
  group: GrantGroup<GrantTool>,
  checked: boolean,
): boolean {
  return group.blocked && !checked;
}

/** The explicit list a save records: the tools named, then each whole group's tools, once each. */
export function expansion(
  catalog: GrantCatalog<GrantTool> | null,
  grants: Grants,
): string[] {
  const tools = [...grants.tools];
  const offered = grantable(catalog);
  for (const group of grants.groups) {
    for (const tool of offered) {
      if (tool.group === group && !tools.includes(tool.tool_id)) {
        tools.push(tool.tool_id);
      }
    }
  }
  return tools;
}

/** The sentence under the grants, naming the groups only when there are some. */
export function expansionText(
  granted: readonly string[],
  groups: readonly string[],
): string {
  if (granted.length === 0) return "This version grants no tools.";
  const from =
    groups.length === 0
      ? "."
      : `, from ${groups.length === 1 ? "the group" : "the groups"} ${groups.join(", ")} and the tools named.`;
  return `This version grants: ${granted.join(", ")}${from}`;
}

/** The grants with a group checked or unchecked. */
export function withGroup<T extends Grants>(
  draft: T,
  group: string,
  checked: boolean,
): T {
  return {
    ...draft,
    groups: checked
      ? [...draft.groups, group]
      : draft.groups.filter((item) => item !== group),
  };
}

/**
 * The grants with a tool checked or unchecked. Unchecking one tool of a whole group means the group
 * isn't whole.
 */
export function withTool<T extends Grants>(
  draft: T,
  tool: Pick<ToolDescriptor, "tool_id" | "group">,
  checked: boolean,
): T {
  return {
    ...draft,
    tools: checked
      ? [...draft.tools, tool.tool_id]
      : draft.tools.filter((item) => item !== tool.tool_id),
    groups: checked
      ? draft.groups
      : draft.groups.filter((item) => item !== tool.group),
  };
}

/**
 * A tool's checkbox: checked when named or granted with its group, and an unavailable one only
 * unchecks.
 */
export function toolGrant(
  tool: Pick<GrantTool, "tool_id" | "group" | "availability">,
  grants: Grants,
): { checked: boolean; unavailable: boolean; locked: boolean } {
  const checked =
    grants.tools.includes(tool.tool_id) || grants.groups.includes(tool.group);
  const unavailable = tool.availability !== "available";
  return { checked, unavailable, locked: unavailable && !checked };
}

/** A tool checkbox's name, which says when every call waits for approval. */
export function toolGrantLabel(
  tool: Pick<ToolDescriptor, "title" | "approval">,
): string {
  return `${tool.title}${tool.approval === "always" ? ", after approval" : ""}`;
}

/** Why a tool can't be granted, and its repair when something here can (PRD-Tool-Catalog TS-03). */
export function unavailableText(tool: ToolState): string {
  const fix = repairText(tool);
  return `${AVAILABILITY_LABEL[tool.availability]}${fix === null ? "" : `. ${fix}`}`;
}
