/**
 * The Expert editor's draft and the revision it saves (WBLD-10). The Draft is the form's model, kept
 * apart from ExpertConfig as contracts keep DTO and UI types distinct. Which profiles new runs may
 * use comes from ModelAvailability.offered (Decision 0013, Decision 0019 S2); the service owns that
 * rule (XWEB-04, WBLD-07). Pure and JSX-free, so `node --test` covers it.
 */
import type {
  ExpertConfig,
  ExpertRevision,
  ExpertView,
  ModelList,
  ModelProfileId,
} from "@autobots/api-client";

import { PROFILE_NAME, profileName } from "../model-profile.ts";
import { withHeld } from "../submit.ts";
import type { Submitted } from "../use-submit.ts";
import type { Grants } from "./grants.ts";

/** The form's fields for one revision. */
export interface Draft extends Grants {
  purpose: string;
  instructions: string;
  /** A profile, or WORKSPACE_SETTING. */
  executor: ModelProfileId | typeof WORKSPACE_SETTING;
  /** The browse domains as typed, one per line or comma-separated (Decision 0035 Y3). */
  browseDomains: string;
}

/** The executor choice that binds no profile, so runs use the workspace's setting. */
export const WORKSPACE_SETTING = "";

/** The draft the latest version holds, with empty defaults. */
export function draftOf(expert: ExpertView): Draft {
  const latest: ExpertConfig = expert.versions.at(-1)?.config ?? {};
  return {
    purpose: latest.purpose ?? "",
    instructions: latest.instructions ?? "",
    tools: latest.tools ?? [],
    groups: latest.tool_groups ?? [],
    executor: latest.role_bindings?.executor ?? WORKSPACE_SETTING,
    browseDomains: (latest.browse_domains ?? []).join("\n"),
  };
}

/** The typed browse domains as a list: split on lines and commas, trimmed, lowercase, once each. */
export function domainsOf(text: string): string[] {
  const listed = text
    .split(/[\n,]/)
    .map((domain) => domain.trim().toLowerCase())
    .filter((domain) => domain !== "");
  return [...new Set(listed)];
}

/** Whether the draft grants browse_goal, directly or by its group, so its domains matter (Y3). */
export function grantsBrowsing(draft: Draft): boolean {
  return (
    draft.tools.includes("browse_goal") || draft.groups.includes("browsing")
  );
}

/** Whether new runs may use a profile, or null while the models aren't read. */
export function offeredFor(
  models: ModelList | null,
  profile: string,
): boolean | null {
  if (models === null) return null;
  return models.models.some(
    (model) => model.profile === profile && model.offered,
  );
}

/**
 * This form edits only the executor. Other offered bindings stay, and one naming a model that isn't
 * offered goes with this save, which the form says, since the service would otherwise refuse it.
 * Until the models are read, every binding stays, and the service refuses one it doesn't offer.
 */
export function splitBindings(
  expert: ExpertView,
  models: ModelList | null,
): { kept: Record<string, ModelProfileId>; dropped: string[] } {
  const saved: Readonly<Record<string, ModelProfileId>> =
    expert.versions.at(-1)?.config.role_bindings ?? {};
  const others = Object.entries(saved).filter(([role]) => role !== "executor");
  return {
    kept: Object.fromEntries(
      others.filter(([, profile]) => offeredFor(models, profile) !== false),
    ),
    dropped: others
      .filter(([, profile]) => offeredFor(models, profile) === false)
      .map(([role]) => role),
  };
}

/** The revision's body, bound to the version the form was read from. */
export function revisionBody(
  expert: ExpertView,
  draft: Draft,
  kept: Readonly<Record<string, ModelProfileId>>,
): ExpertRevision {
  return {
    expected_version: expert.latest_version,
    config: {
      // What this form doesn't edit, such as skills, stays as it was.
      ...expert.versions.at(-1)?.config,
      purpose: draft.purpose,
      instructions: draft.instructions,
      tools: [...draft.tools],
      tool_groups: [...draft.groups],
      browse_domains: domainsOf(draft.browseDomains),
      role_bindings: {
        ...kept,
        ...(draft.executor === WORKSPACE_SETTING
          ? {}
          : { executor: draft.executor }),
      },
    },
  };
}

/** The editor's words for a refusal's code; `model_not_offered` says the service's own. */
export const SAVE_REFUSALS: Readonly<Record<string, string>> = {
  owner_required: "Only the workspace owner can save a revision.",
  expert_version_conflict: "Someone saved a newer version. Reload to see it.",
  expert_tool_unavailable:
    "A granted tool is unavailable in this install. Remove it, or configure it first.",
  expert_tool_group_empty: "A granted group has no tools an Expert may use.",
};

export const SAVE_LOST =
  "The reply was lost, so it may have been saved. Pressing again won't save it twice.";

/** What revisionText reads from a save's reply. */
export type RevisionReply = Pick<
  Submitted<ExpertView>,
  "outcome" | "value" | "refusal" | "held"
>;

/** A save's words: the version it made, a lost reply, or why it was refused. */
export function revisionText(result: RevisionReply): string {
  if (result.outcome === "accepted" && result.value !== null) {
    return `Saved as version ${result.value.latest_version}. Work already started keeps its version.`;
  }
  if (result.outcome === "unknown") return SAVE_LOST;
  const failure = result.refusal;
  const words =
    failure?.code === "model_not_offered"
      ? failure.message
      : (SAVE_REFUSALS[failure?.code ?? ""] ?? "That could not be saved.");
  return withHeld(words, result.held);
}

/** The executor's choices besides the workspace setting. */
export interface ExecutorOptions {
  offered: readonly { profile: ModelProfileId; label: string }[];
  /**
   * The saved choice when it isn't offered, which stays shown so the form never changes it unasked:
   * as it is until the models are read, then disabled.
   */
  saved: { label: string; disabled: boolean } | null;
}

/** Each profile /api/models offers, and the saved choice when it isn't one of them. */
export function executorOptions(
  value: string,
  models: ModelList | null,
): ExecutorOptions {
  const offered = (models?.models ?? [])
    .filter((model) => model.offered)
    .map((model) => ({
      profile: model.profile,
      label: PROFILE_NAME[model.profile],
    }));
  const listed =
    value === WORKSPACE_SETTING ||
    offered.some((option) => option.profile === value);
  if (listed) return { offered, saved: null };
  return {
    offered,
    saved:
      models === null
        ? { label: profileName(value), disabled: false }
        : {
            label: `${value}: not offered for new runs until qualified`,
            disabled: true,
          },
  };
}

/** A version's granted tools and groups, as the version list shows them. */
export function versionToolsText(config: ExpertConfig): string {
  const groups = config.tool_groups ?? [];
  return `${config.tools?.join(", ") || "no tools"}${
    groups.length === 0 ? "" : ` (groups: ${groups.join(", ")})`
  }`;
}
