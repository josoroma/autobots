import type { ModelList } from "@autobots/api-client";

import { Select } from "@/components/ui/field";
import { LoadState } from "@/components/ui/load-state";
import { executorOptions, WORKSPACE_SETTING } from "@/lib/experts/draft";
import type { Resource } from "@/lib/use-resource";

/**
 * The executor's choices: the workspace setting and each profile /api/models offers. A saved choice
 * that isn't offered stays shown and disabled, so the form never changes it unasked.
 */
function ExecutorChoice({
  value,
  models,
  disabled,
  onChange,
}: {
  value: string;
  models: ModelList | null;
  disabled: boolean;
  onChange: (profile: string) => void;
}) {
  const { offered, saved } = executorOptions(value, models);
  return (
    <Select
      id="executor"
      value={value}
      disabled={disabled}
      className="sm:max-w-xs"
      onChange={(event) => onChange(event.target.value)}
    >
      <option value={WORKSPACE_SETTING}>Workspace setting</option>
      {offered.map((option) => (
        <option key={option.profile} value={option.profile}>
          {option.label}
        </option>
      ))}
      {saved === null ? null : (
        <option value={value} disabled={saved.disabled}>
          {saved.label}
        </option>
      )}
    </Select>
  );
}

/**
 * The model for the Expert's work, the models read's own failure, and the roles whose saved model a
 * save removes because new runs may not use it (Decision 0013, Decision 0019 S2).
 */
export function ExecutorField({
  value,
  models,
  held,
  dropped,
  onChange,
}: {
  value: string;
  models: Resource<ModelList>;
  held: boolean;
  dropped: readonly string[];
  onChange: (profile: string) => void;
}) {
  return (
    <>
      <div className="space-y-1.5 border-t pt-5">
        <label htmlFor="executor" className="text-sm font-medium">
          Model for its work
        </label>
        <ExecutorChoice
          value={value}
          models={models.value}
          disabled={held}
          onChange={onChange}
        />
        {models.state.kind === "loading" ? null : (
          <LoadState
            state={models.state}
            what="the models new runs may use"
            onRetry={models.reload}
            pending={models.pending}
          />
        )}
      </div>
      {dropped.length === 0 ? null : (
        <p
          data-field="dropped-bindings"
          className="rounded-lg border p-3 text-sm"
        >
          The saved version names a model that isn&apos;t offered for new runs
          for {dropped.join(", ")}. Saving removes that.
        </p>
      )}
    </>
  );
}
