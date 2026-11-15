import {
  parseModelList,
  parseModelPolicyState,
  type ModelList,
  type ModelPolicyState,
} from "@autobots/api-client";

import { useResource, type ResourceState } from "@/lib/use-resource";

function failed(state: ResourceState<unknown>): boolean {
  return (
    state.kind !== "idle" && state.kind !== "loading" && state.kind !== "ready"
  );
}

/**
 * The models and the workspace's policy, which the disclosure reads together: neither is shown
 * until both are read, and either failing says the choice can't be read. Reading starts nothing.
 */
export function useDisclosureReads(): {
  models: ModelList | null;
  policy: ModelPolicyState | null;
  failed: boolean;
} {
  const models = useResource("/api/models", parseModelList);
  const policy = useResource(
    "/api/settings/model-policy",
    parseModelPolicyState,
  );
  const both =
    models.state.kind === "ready" && policy.state.kind === "ready"
      ? { models: models.state.value, policy: policy.state.value }
      : { models: null, policy: null };
  return { ...both, failed: failed(models.state) || failed(policy.state) };
}
