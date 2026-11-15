/**
 * The policy screen's one initial read (WSYS-03, XDUP-18): the approved models and the saved
 * policy, read side by side. A failure of either shows why in place of the form, the one a person
 * must act on first (XERR-04), with Retry for an outage.
 */
import {
  parseModelList,
  parseModelPolicyState,
  type ModelList,
  type ModelPolicyState,
} from "@autobots/api-client";

import { worstFailure } from "@/lib/load";
import { useResource, type ResourceState } from "@/lib/use-resource";

const LOADING: ResourceState<unknown> = { kind: "loading" };

export interface PolicyRead {
  models: ModelList | null;
  policy: ModelPolicyState | null;
  /** What shows while either is missing: loading, or the failure to act on first. */
  state: ResourceState<unknown>;
  pending: boolean;
  retry: () => void;
}

export function usePolicyRead(): PolicyRead {
  const models = useResource("/api/models", parseModelList);
  const policy = useResource(
    "/api/settings/model-policy",
    parseModelPolicyState,
  );
  return {
    models: models.value,
    policy: policy.value,
    state: worstFailure([models.state, policy.state]) ?? LOADING,
    pending: models.pending || policy.pending,
    retry: () => {
      models.reload();
      policy.reload();
    },
  };
}
