import {
  getModelPolicy,
  getModels,
  getModelSource,
  type ModelList,
  type ModelPolicyState,
} from "@autobots/api-client";

import { readOf } from "@/lib/load";
import { useResource, type ResourceState } from "@/lib/use-resource";

function failed(state: ResourceState<unknown>): boolean {
  return (
    state.kind !== "idle" && state.kind !== "loading" && state.kind !== "ready"
  );
}

export type ModelSourceName = "openrouter" | "local";

/**
 * The models, the workspace's policy and its Model source, which the disclosure reads together:
 * none is shown until all are read, and any failing says the choice can't be read. Reading starts
 * nothing. The source decides where the disclosure says model calls go (Decision 0041 A13).
 */
export function useDisclosureReads(): {
  models: ModelList | null;
  policy: ModelPolicyState | null;
  source: ModelSourceName | null;
  failed: boolean;
} {
  const models = useResource(readOf(getModels));
  const policy = useResource(readOf(getModelPolicy));
  const source = useResource(readOf(getModelSource));
  const all =
    models.state.kind === "ready" &&
    policy.state.kind === "ready" &&
    source.state.kind === "ready"
      ? {
          models: models.state.value,
          policy: policy.state.value,
          source: source.state.value.source,
        }
      : { models: null, policy: null, source: null };
  return {
    ...all,
    failed:
      failed(models.state) || failed(policy.state) || failed(source.state),
  };
}
