/**
 * The Experts list's classification and card words (WBLD-12). Tool classes and approval come from
 * the catalog (PRD-Studio EX-02, EX-03), so until it's read no Expert is called read only. Pure and
 * JSX-free, so `node --test` covers it.
 */
import type {
  ExpertConfig,
  ExpertView,
  ToolDescriptor,
} from "@autobots/api-client";

import { formatRelative } from "../format.ts";
import { PROFILE_NAME } from "../model-profile.ts";

/** What the list reads from the catalog, by tool ID. */
export type CatalogTools = ReadonlyMap<
  string,
  Pick<ToolDescriptor, "operation_class" | "approval">
>;

export type ExpertFilter = "all" | "outside" | "read_only";

export const EXPERT_FILTERS: readonly (readonly [ExpertFilter, string])[] = [
  ["all", "All"],
  ["outside", "Can change things outside"],
  ["read_only", "Read only"],
];

export const EXPERT_FILTER_IDS: readonly ExpertFilter[] = EXPERT_FILTERS.map(
  ([id]) => id,
);

/** One Expert and whether it can change something outside, or null while the catalog is unread. */
export interface ClassifiedExpert {
  expert: ExpertView;
  outside: boolean | null;
}

function latestConfig(expert: ExpertView): ExpertConfig {
  return expert.versions.at(-1)?.config ?? {};
}

/** Each Expert's class from its latest version's tools, unknown for all while the catalog is null. */
export function classify(
  experts: readonly ExpertView[],
  catalog: CatalogTools | null,
): ClassifiedExpert[] {
  return experts.map((expert) => ({
    expert,
    outside:
      catalog === null
        ? null
        : (latestConfig(expert).tools ?? []).some(
            (tool) =>
              catalog.get(tool)?.operation_class ===
              "consequential_external_write",
          ),
  }));
}

/** Whether a filter holds an Expert. An unknown class is in neither class filter. */
export function inExpertFilter(
  item: ClassifiedExpert,
  filter: ExpertFilter,
): boolean {
  if (filter === "all") return true;
  return item.outside === (filter === "outside");
}

/** The letter on an Expert's tile. */
export function initialOf(name: string): string {
  return name.trim().charAt(0).toUpperCase();
}

/** The executor's profile and the latest version, such as "executor · Terra · version 1". */
export function executorLine(expert: ExpertView): string {
  const executor = latestConfig(expert).role_bindings?.executor;
  const name =
    executor === undefined ? "Workspace default" : PROFILE_NAME[executor];
  return `executor · ${name} · version ${expert.latest_version}`;
}

/** How many runs an Expert has had, and when the last was, measured from when the list was read. */
export function runsLine(expert: ExpertView, now: number): string {
  if (expert.run_count === 0) return "No runs yet";
  const runs = `${expert.run_count} ${expert.run_count === 1 ? "run" : "runs"}`;
  return expert.last_run_at === null
    ? runs
    : `${runs} · last run ${formatRelative(expert.last_run_at, now)}`;
}

// The noun each always-approved tool decides on, for "Approval on every issue".
const APPROVAL_NOUN: Readonly<Record<string, string>> = {
  create_github_issue: "issue",
  github_open_pull_request: "pull request",
};

/**
 * What waits for a person, when the latest version grants an always-approved tool; else null. A
 * tool approved only while YOLO is off says so (Decision 0035 Y2).
 */
export function approvalNote(
  tools: readonly string[],
  catalog: CatalogTools | null,
): string | null {
  const approvalOf = (tool: string) => catalog?.get(tool)?.approval;
  const approvals = tools.filter((tool) => {
    const approval = approvalOf(tool);
    return approval === "always" || approval === "unless_yolo";
  });
  if (approvals.length === 0) return null;
  const noun =
    approvals.length === 1
      ? (APPROVAL_NOUN[approvals[0] ?? ""] ?? "call")
      : "call to these tools";
  const onlyWithoutYolo = approvals.every(
    (tool) => approvalOf(tool) === "unless_yolo",
  );
  return `Approval on every ${noun}${onlyWithoutYolo ? ", while YOLO is off" : ""}`;
}

/**
 * Where an Expert that grants browse_goal may browse, or that it can't until its domains are listed
 * (Decision 0035 Y3, Y14); else null.
 */
export function browseDomainsLine(config: ExpertConfig): string | null {
  if (!(config.tools ?? []).includes("browse_goal")) return null;
  const domains = config.browse_domains ?? [];
  return domains.length === 0
    ? "No browse domains yet, so it can't browse"
    : `Browses ${domains.join(", ")}`;
}

/** The tool chips a card shows. */
export const SHOWN_TOOLS = 4;

/** The first tools, how many more there are, then the groups, or "no tools". */
export function toolChips(config: ExpertConfig): string[] {
  const tools = config.tools ?? [];
  const groups = config.tool_groups ?? [];
  if (tools.length === 0 && groups.length === 0) return ["no tools"];
  return [
    ...tools.slice(0, SHOWN_TOOLS),
    ...(tools.length > SHOWN_TOOLS ? [`+${tools.length - SHOWN_TOOLS}`] : []),
    ...(groups.length === 0 ? [] : [`groups: ${groups.join(", ")}`]),
  ];
}
