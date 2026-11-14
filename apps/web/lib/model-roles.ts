/**
 * Rules about a run's role bindings that the run page, the disclosure before a run and Settings →
 * Models each state, written once (WRUN-11, R-37). The screens only disclose them; routing stays in
 * the service. Pure and JSX-free.
 */
import type { BindingSource, ModelRole } from "@autobots/api-client";

const EXECUTOR: ModelRole = "executor";
const SUMMARIZER: ModelRole = "summarizer";

/** PRD-Studio MD-02: which step of MP-01's order chose a role's binding. */
export const BINDING_SOURCE_LABEL: Readonly<Record<BindingSource, string>> = {
  run_override: "Run override",
  workspace_override: "Workspace override",
  workspace_default: "Workspace default",
  builtin_default: "Built-in default",
};

/** A role's binding, as the frozen role map, the policy and the disclosure each hold it. */
export interface Bound {
  role: string;
  profile: string;
}

/** The roles, other than the executor, bound to a different profile. Only the executor dispatches. */
export function differingRoles(bindings: readonly Bound[]): string[] {
  const executor = bindings.find((binding) => binding.role === EXECUTOR);
  return bindings
    .filter(
      (binding) =>
        binding.role !== EXECUTOR && binding.profile !== executor?.profile,
    )
    .map((binding) => binding.role);
}

/**
 * Whether a run would pause with route_not_bound when it needs compaction: unless the summarizer is
 * bound to the executor's profile, as goal_loop's _summary_route requires, compaction has no route.
 * No summarizer binding at all differs too.
 */
export function summarizerDiffers(bindings: readonly Bound[]): boolean {
  const executor = bindings.find((binding) => binding.role === EXECUTOR);
  const summarizer = bindings.find((binding) => binding.role === SUMMARIZER);
  return summarizer === undefined || summarizer.profile !== executor?.profile;
}
