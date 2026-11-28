import type {
  ModelAvailability,
  ModelPolicyState,
  RoleBinding,
} from "@autobots/api-client";

import { Button } from "@/components/ui/button";
import { fieldIds, Select } from "@/components/ui/field";
import {
  BUILTIN_DEFAULT,
  CHOOSE_LOCAL,
  choices,
  followingCount,
  LOCAL_ROLES,
  sourceText,
  WORKSPACE_DEFAULT,
  type PolicyDraft,
} from "@/lib/model-policy";
import { cn } from "@/lib/utils";

// One role per row: its name on the left and its native select on the right (Decision 0021).
const ROW = "border-border flex items-center gap-2.5 border-t py-[7px]";
const ROW_CONTROL = "ml-auto w-40 shrink-0 sm:w-56";

/** The profiles a select lists. One that's listed only because it's chosen can't be picked again. */
function ProfileOptions({
  models,
  current,
}: {
  models: readonly ModelAvailability[];
  current: string | undefined;
}) {
  return choices(models, current).map((model) => (
    <option key={model.profile} value={model.profile} disabled={!model.offered}>
      {model.canonical_id}
    </option>
  ));
}

// On Local the default is the Local default, so the built-in one isn't offered (Decision 0041 A8).
// With none saved, the select says so and can't be saved as it is.
function DefaultNone({ local, value }: { local: boolean; value: string }) {
  if (!local) {
    return (
      <option value={BUILTIN_DEFAULT}>
        Built-in default (Sol for researcher, Terra otherwise)
      </option>
    );
  }
  return value === BUILTIN_DEFAULT ? (
    <option value={BUILTIN_DEFAULT} disabled>
      {CHOOSE_LOCAL}
    </option>
  ) : null;
}

function WorkspaceDefaultRow({
  local,
  models,
  value,
  onChange,
}: {
  local: boolean;
  models: readonly ModelAvailability[];
  value: string;
  onChange: (profile: string) => void;
}) {
  return (
    <div className="border-border border-b">
      <div className={ROW}>
        <label
          htmlFor="workspace-default"
          className="min-w-0 text-body font-medium"
        >
          Workspace default
        </label>
        <div className={cn(ROW_CONTROL, "w-44 sm:w-80")}>
          <Select
            id="workspace-default"
            value={value}
            onChange={(event) => onChange(event.target.value)}
          >
            <DefaultNone local={local} value={value} />
            <ProfileOptions models={models} current={value} />
          </Select>
        </div>
      </div>
    </div>
  );
}

// PRD-Studio MD-02: the role, which step chose its saved binding, and its override.
function RoleOverrideRow({
  models,
  binding,
  value,
  onChange,
}: {
  models: readonly ModelAvailability[];
  binding: RoleBinding;
  value: string | undefined;
  onChange: (profile: string) => void;
}) {
  const id = `role-${binding.role}`;
  return (
    <div className={ROW}>
      <div className="min-w-0">
        <label htmlFor={id} className="block font-mono text-meta break-all">
          {binding.role}
        </label>
        <span
          id={fieldIds(id).description}
          data-binding-source={binding.source}
          className="text-muted-foreground block text-caption"
        >
          {sourceText(binding.source)}
          {", "}
          {binding.canonical_id}
        </span>
      </div>
      <div className={ROW_CONTROL}>
        <Select
          id={id}
          aria-describedby={fieldIds(id).description}
          value={value ?? WORKSPACE_DEFAULT}
          onChange={(event) => onChange(event.target.value)}
        >
          <option value={WORKSPACE_DEFAULT}>Workspace default</option>
          <ProfileOptions models={models} current={value} />
        </Select>
      </div>
    </div>
  );
}

export interface PolicyFormProps {
  /** The workspace is on the Local source (Decision 0041 A1, A8). */
  local: boolean;
  models: readonly ModelAvailability[];
  saved: ModelPolicyState;
  draft: PolicyDraft;
  dirty: boolean;
  pending: boolean;
  onDefault: (profile: string) => void;
  onOverride: (role: string, profile: string) => void;
  onSave: () => void;
  onDiscard: () => void;
  onReset: () => void;
}

/** The workspace default, one override per role, and Save, Discard and Reset all (PRD-Studio MD-02, MD-03). */
export function PolicyForm(props: PolicyFormProps) {
  const { local, models, saved, draft, pending } = props;
  const bindings = saved.policy.bindings;
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        props.onSave();
      }}
      className="space-y-5"
    >
      <WorkspaceDefaultRow
        local={local}
        models={models}
        value={draft.defaultProfile}
        onChange={props.onDefault}
      />
      {local ? (
        <p data-field="local-roles" className="text-muted-foreground text-body">
          {LOCAL_ROLES}
        </p>
      ) : (
        <fieldset className="min-w-0">
          <legend className="mb-2 text-sm font-semibold">Role overrides</legend>
          <div className="border-border grid gap-x-8 border-b md:grid-cols-2">
            {bindings.map((binding) => (
              <RoleOverrideRow
                key={binding.role}
                models={models}
                binding={binding}
                value={draft.overrides[binding.role]}
                onChange={(profile) => props.onOverride(binding.role, profile)}
              />
            ))}
          </div>
        </fieldset>
      )}
      <div className="border-border flex flex-wrap items-center gap-3 border-t pt-4">
        <Button type="submit" size="lg" disabled={pending}>
          {pending ? "Saving" : "Save policy"}
        </Button>
        <Button
          type="button"
          variant="outline"
          size="lg"
          disabled={pending || !props.dirty}
          onClick={props.onDiscard}
        >
          Discard
        </Button>
        {local ? null : (
          <Button
            type="button"
            variant="outline"
            size="lg"
            disabled={pending}
            onClick={props.onReset}
          >
            Reset all
          </Button>
        )}
        <p
          data-field="policy-summary"
          className="text-muted-foreground ml-auto text-ui tabular-nums"
        >
          {followingCount(bindings)} of {bindings.length} roles follow the
          workspace default
        </p>
      </div>
    </form>
  );
}
