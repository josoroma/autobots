/**
 * The policy screen's one initial read (WSYS-03, XDUP-18): the approved models, the saved policy
 * and the Model source they belong to (Decision 0041 A1), read side by side. A failure of any shows
 * why in place of the form, the one a person must act on first (XERR-04), with Retry for an outage.
 */
import {
  getModelPolicy,
  getModels,
  getModelSource,
  type ModelList,
  type ModelPolicyState,
  type ModelSourceState,
} from "@autobots/api-client";

import { readOf, worstFailure } from "@/lib/load";
import { useResource, type ResourceState } from "@/lib/use-resource";

const LOADING: ResourceState<unknown> = { kind: "loading" };

export interface PolicyRead {
  models: ModelList | null;
  policy: ModelPolicyState | null;
  source: ModelSourceState["source"] | null;
  /** What shows while any is missing: loading, or the failure to act on first. */
  state: ResourceState<unknown>;
  pending: boolean;
  retry: () => void;
}

export function usePolicyRead(): PolicyRead {
  const models = useResource(readOf(getModels));
  const policy = useResource(readOf(getModelPolicy));
  const source = useResource(readOf(getModelSource));
  return {
    models: models.value,
    policy: policy.value,
    source: source.value?.source ?? null,
    state: worstFailure([models.state, policy.state, source.state]) ?? LOADING,
    pending: models.pending || policy.pending || source.pending,
    retry: () => {
      models.reload();
      policy.reload();
      source.reload();
    },
  };
}
