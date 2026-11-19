/**
 * The tool catalog's words, shared by the Tools page and the Expert editor (WTAP-07, R-37). Each
 * table is keyed by its ToolDescriptor union, so a value the contract gains fails the type check
 * here until it has words (WTAP-06). Every state is said in words; a badge never stands for one
 * alone (PRD-Tool-Catalog TS-01 to TS-03). Pure and JSX-free.
 */
import type { ToolDescriptor, ToolGroupDescriptor } from "@autobots/api-client";

export const PROVIDER_LABEL: Readonly<
  Record<ToolDescriptor["provider"], string>
> = {
  autobots: "Autobots, on this Mac",
  tavily: "Tavily",
  jina: "Jina",
  serpapi: "SerpApi (Google)",
  direct: "Directly from each site",
  yahoo_finance: "Yahoo Finance",
  world_bank: "World Bank",
  github: "GitHub",
};

export const OPERATION_CLASS_LABEL: Readonly<
  Record<ToolDescriptor["operation_class"], string>
> = {
  pure: "Pure",
  read_only: "Read only",
  reversible_internal_write: "Writes inside the run",
  consequential_external_write: "Changes something outside",
  arbitrary_execution: "Arbitrary execution",
};

export const COST_LABEL: Readonly<
  Record<ToolDescriptor["cost_class"], string>
> = {
  free_local: "No provider charge",
  metered_provider: "Metered by its provider",
};

export const AVAILABILITY_LABEL: Readonly<
  Record<ToolDescriptor["availability"], string>
> = {
  available: "Available",
  key_missing: "Unavailable: key not set",
  disabled_by_policy: "Unavailable: disabled by policy",
  not_qualified: "Unavailable: not qualified",
};

/** The availabilities the Tools page filters by. */
export const AVAILABILITY_FILTERS: readonly ToolDescriptor["availability"][] = [
  "available",
  "key_missing",
  "disabled_by_policy",
];

// Decision 0026 C9: `by_action` tools hold only some actions for a person.
export const APPROVAL_TEXT: Readonly<
  Record<ToolDescriptor["approval"], string>
> = {
  always: "Every call waits for a person",
  // Decision 0035 Y2: browse_goal, whose calls start without asking while YOLO is on.
  unless_yolo: "Every call waits for a person, unless YOLO is on",
  by_action: "Some actions wait for a person",
  never: "Not needed",
};

// Decisions 0024, 0025 and 0032 G7: these keys can also be saved per workspace in Settings → Keys &
// vars.
const SAVABLE_KEYS: Readonly<Record<string, string>> = {
  tavily: "Tavily",
  jina: "Jina",
  serpapi: "SerpApi",
};

/** What the key and repair words read from a tool. */
export type ToolState = Pick<
  ToolDescriptor,
  "availability" | "availability_reason" | "key_requirement"
>;

/** PK-05: where a tool's key comes from, never the key. Null for a tool that needs none. */
export function keySource(tool: ToolState): string | null {
  const requirement = tool.key_requirement;
  if (!requirement) return null;
  const names = requirement.variables.join(", ");
  if (requirement.source === "settings") {
    return "Key saved in Settings → Keys & vars for this workspace";
  }
  if (requirement.source === "environment") {
    return `${names}, from the server environment or .env`;
  }
  return `${names}, not set`;
}

/** A catalog row's short form of keySource, for an available tool whose key has a source. */
export function keyOrigin(tool: ToolState): string | null {
  const source = tool.key_requirement?.source ?? null;
  if (tool.availability !== "available" || source === null) return null;
  return source === "settings"
    ? "Key from Settings"
    : "Key from the environment";
}

/** TS-03: how to make an unavailable tool available, or null when nothing here can. */
export function repairText(tool: ToolState): string | null {
  if (tool.availability === "key_missing" && tool.key_requirement) {
    const names = tool.key_requirement.variables.join(" and ");
    const savable = SAVABLE_KEYS[tool.key_requirement.credential];
    if (savable !== undefined) {
      return `Save a ${savable} key in Settings → Keys & vars, or set ${names} in .env, then restart the worker and the API.`;
    }
    // PRD-Studio GH-07: names and permissions only, never a value.
    const scopes =
      tool.key_requirement.scopes.length === 0
        ? ""
        : ` The token needs these permissions on that repository only: ${tool.key_requirement.scopes.join(", ")}.`;
    return `Save them in Settings → Keys & vars, or set ${names} in .env.${scopes} After a change to .env, restart the worker and the API.`;
  }
  // Decision 0033 W2: a switch the owner turned off says how to turn it back on.
  if (tool.availability_reason === "turned_off") {
    return "Turned off for this workspace. The workspace owner can turn it on here in Tools.";
  }
  if (tool.availability_reason === "group_turned_off") {
    return "Its group is turned off for this workspace. The workspace owner can turn the group on here in Tools.";
  }
  if (tool.availability_reason === "isolated_executor_not_qualified") {
    return "Disabled until the isolated browser executor is qualified and browsing is turned on in Settings → Keys & vars or .env. See the operations runbook.";
  }
  if (tool.availability === "not_qualified") {
    return "Waits for its provider's qualification.";
  }
  return null;
}

/** Where a tool's calls go, in words (PRD-Tool-Catalog TS-01). */
export function networkText(network: boolean): string {
  return network ? "Leaves this Mac" : "Stays on this Mac";
}

/** A tool's cost class, with its provider's note when it has one. */
export function costText(
  tool: Pick<ToolDescriptor, "cost_class" | "cost_note">,
): string {
  return `${COST_LABEL[tool.cost_class]}${tool.cost_note ? `, ${tool.cost_note}` : ""}`;
}

/**
 * A catalog row's facts after its ID: provider, class, where it runs, cost and, for an available
 * tool, where its key comes from (PRD-Tool-Catalog TS-01).
 */
export function rowFacts(
  tool: Pick<
    ToolDescriptor,
    "provider" | "operation_class" | "network" | "cost_class"
  > &
    ToolState,
): string {
  const origin = keyOrigin(tool);
  return `· ${PROVIDER_LABEL[tool.provider]} · ${OPERATION_CLASS_LABEL[tool.operation_class]} · ${networkText(tool.network)} · ${COST_LABEL[tool.cost_class]}${origin === null ? "" : ` · ${origin}`}`;
}

/** A registered tool's limits, or that it has none registered. */
export function limitsText(limits: ToolDescriptor["limits"]): string {
  return limits
    ? `${limits.timeout_seconds} s, ${limits.retries} retries, ${limits.max_output_bytes} output bytes`
    : "Not registered";
}

/** What can grant a tool, such as "workflow node". */
export function grantorText(
  grantor: ToolDescriptor["grantable_to"][number],
): string {
  return grantor.replaceAll("_", " ");
}

/** A field's constraints as the schema states them, such as `minimum 0, maxItems 100`, or None. */
export function constraintText(
  constraints: Readonly<Record<string, unknown>>,
): string {
  const entries = Object.entries(constraints);
  if (entries.length === 0) return "None";
  return entries
    .map(([key, value]) => `${key} ${JSON.stringify(value)}`)
    .join(", ");
}

/** Decision 0033 W5: a tool's switch state in words, or null for a tool no switch applies to. */
export function switchText(
  tool: Pick<ToolDescriptor, "switch">,
): string | null {
  const state = tool.switch;
  if (!state) return null;
  if (state.by === "group") return "Off with its group";
  if (state.by === "tool") return "Off for this workspace";
  return "On for this workspace";
}

/** A group's switch state in words, or null for a group no switch applies to. */
export function groupSwitchText(
  group: Pick<ToolGroupDescriptor, "switch">,
): string | null {
  if (!group.switch) return null;
  return group.switch.enabled
    ? "Group on for this workspace"
    : "Group off for this workspace";
}

export const SWITCH_SAVED = "Saved. The switch applies to the next call.";
