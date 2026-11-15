/**
 * What the disclosure before a run says it would use (PRD-Model-Providers MP-07): each role's
 * binding after an Expert's own and a run-wide choice, and the server's rule that any binding not
 * offered refuses the whole run. It only discloses; admission decides. Pure and JSX-free.
 */
import type { ModelList, ModelPolicyState } from "@autobots/api-client";

const EXECUTOR = "executor";
/** The select's value for "the workspace setting". */
export const WORKSPACE_DEFAULT = "";

export interface Binding {
  role: string;
  profile: string;
}

export interface DisclosureInputs {
  models: ModelList | null;
  policy: ModelPolicyState | null;
  /** The run-wide choice, or WORKSPACE_DEFAULT. */
  chosen: string;
  /** An Expert's own role bindings, which a run-wide choice doesn't replace. */
  roleOverrides: Readonly<Record<string, unknown>> | undefined;
  /** False for a workflow version with no agent step, which calls no model and isn't refused. */
  usesModel: boolean;
  /** The models or the policy couldn't be read. */
  failed: boolean;
}

export interface Disclosure {
  bindings: Binding[];
  executor: Binding | null;
  /** Pressing Run would start nothing, since a binding isn't offered. */
  refused: boolean;
  /** A binding not offered is in the Expert's saved version, which settings don't change. */
  fromExpert: boolean;
  /** The model, roles and summarizer note appear only once the choice is read and allowed. */
  showModel: boolean;
}

export function resolveDisclosure(inputs: DisclosureInputs): Disclosure {
  const { models, policy, chosen, roleOverrides, usesModel, failed } = inputs;
  // An Expert's binding outranks the workspace and a run's own choice.
  const bindings = (policy?.policy.bindings ?? []).map((binding) => {
    const expert = roleOverrides?.[binding.role];
    const profile =
      typeof expert === "string"
        ? expert
        : chosen !== WORKSPACE_DEFAULT
          ? chosen
          : binding.profile;
    return { role: binding.role, profile };
  });
  const executor =
    bindings.find((binding) => binding.role === EXECUTOR) ?? null;
  // The server's own rule: any binding that isn't offered refuses the whole run.
  const notOffered = (profile: unknown): boolean =>
    models?.models.find((model) => model.profile === profile)?.offered ===
    false;
  const refused =
    usesModel && bindings.some((binding) => notOffered(binding.profile));
  return {
    bindings,
    executor,
    refused,
    fromExpert: Object.values(roleOverrides ?? {}).some(notOffered),
    showModel: !failed && executor !== null && !refused,
  };
}

/** A profile's canonical model id, or the profile itself until the models are read. */
export function canonicalOf(models: ModelList | null, profile: string): string {
  return (
    models?.models.find((model) => model.profile === profile)?.canonical_id ??
    profile
  );
}
