"use client";

import {
  parseModelList,
  parseModelPolicyState,
  type ModelList,
  type ModelPolicyState,
} from "@autobots/api-client";
import { Info, TriangleAlert } from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Card, INNER_BOX } from "@/components/ui/card";
import { Select } from "@/components/ui/field";
import { csrfFetch } from "@/lib/csrf-fetch";
import { cn } from "@/lib/utils";

const WORKSPACE_DEFAULT = "";
const EXECUTOR = "executor";
const SUMMARIZER = "summarizer";

// One role per row: its name on the left and its native select on the right (Decision 0021).
const ROW = "border-border flex items-center gap-2.5 border-t py-[7px]";
const ROW_CONTROL = "ml-auto w-40 shrink-0 sm:w-56";

function modelLabel(canonicalId: string, wireId: string): string {
  return `${canonicalId} (requested as ${wireId})`;
}

// Only what's saved is described, so the screen can't say a draft has taken effect.
function RoleEffect({ state }: { state: ModelPolicyState }) {
  const bindings = state.policy.bindings;
  const executor = bindings.find((binding) => binding.role === EXECUTOR);
  const differing = bindings.filter(
    (binding) =>
      binding.role !== EXECUTOR && binding.profile !== executor?.profile,
  );
  return (
    <div
      data-field="role-effect"
      className={cn(INNER_BOX, "flex gap-3 px-3.5 text-[13.5px]")}
    >
      <Info
        aria-hidden="true"
        className="text-muted-foreground mt-0.5 size-4 shrink-0"
      />
      <div className="min-w-0 space-y-1">
        <p>
          Only the executor&apos;s binding dispatches in this release. Other
          roles that differ from it don&apos;t take effect.
        </p>
        {differing.length === 0 ? (
          <p data-role-effect="same">
            Every role has the same binding as the executor now.
          </p>
        ) : (
          <p data-role-effect="differs">
            These differ from the executor, so they don&apos;t take effect:{" "}
            {differing.map((binding) => binding.role).join(", ")}.
          </p>
        )}
        <p>
          A summarizer that differs pauses the run with route_not_bound, once
          the run needs compaction.
        </p>
        {differing.some((binding) => binding.role === SUMMARIZER) ? (
          <p data-role-effect="summarizer" className="font-medium">
            The summarizer differs here, so long runs will pause that way.
          </p>
        ) : null}
      </div>
    </div>
  );
}

export function ModelPolicyPanel() {
  const [models, setModels] = useState<ModelList | null>(null);
  const [state, setState] = useState<ModelPolicyState | null>(null);
  const [defaultProfile, setDefaultProfile] = useState("");
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  const adopt = useCallback((next: ModelPolicyState) => {
    setState(next);
    setDefaultProfile(next.default_profile);
    setOverrides(next.role_overrides as Record<string, string>);
  }, []);

  useEffect(() => {
    let active = true;
    Promise.all([
      fetch("/api/models", { cache: "no-store" }),
      fetch("/api/settings/model-policy", { cache: "no-store" }),
    ])
      .then(async ([modelReply, policyReply]) => {
        if (!active) return;
        if (!modelReply.ok || !policyReply.ok) {
          // Read, or an unread refusal holds its connection open for as long as the page lives.
          await Promise.all([modelReply.text(), policyReply.text()]);
          setFailed(true);
          return;
        }
        setModels(parseModelList(await modelReply.json()));
        adopt(parseModelPolicyState(await policyReply.json()));
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
    };
  }, [adopt]);

  async function save(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (state === null) return;
    setBusy(true);
    setMessage(null);
    const reply = await csrfFetch("/api/settings/model-policy", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        expected_version: state.version,
        default_profile: defaultProfile,
        role_overrides: overrides,
      }),
    }).catch(() => null);
    setBusy(false);
    if (reply?.ok === true) {
      adopt(parseModelPolicyState(await reply.json()));
      setMessage("Saved. New runs freeze this, and admitted runs keep theirs.");
      return;
    }
    const failure = (await reply?.json().catch(() => null)) as {
      code?: string;
      message?: string;
    } | null;
    setMessage(
      failure?.code === "stale_version"
        ? "This policy changed after you opened it, so nothing was saved. Reload the page and try again."
        : (failure?.message ?? "That did not save. Nothing changed."),
    );
  }

  if (failed) {
    return (
      <Card>
        <p role="alert" data-state="policy-unavailable" className="text-sm">
          The model policy is unavailable. Sign in, and check that the local API
          is running.
        </p>
      </Card>
    );
  }
  if (models === null || state === null) {
    return <p className="text-muted-foreground text-sm">Loading models.</p>;
  }
  // A saved choice that isn't offered stays visible, unselectable, so the page never shows another.
  const listed = models.models;
  const choices = (current: string | undefined) =>
    listed.filter((model) => model.offered || model.profile === current);
  const notOffered = new Set(
    listed.filter((model) => !model.offered).map((model) => model.profile),
  );
  const savedChoiceNotOffered =
    notOffered.has(state.default_profile) ||
    Object.values(state.role_overrides).some((profile) =>
      notOffered.has(profile as (typeof listed)[number]["profile"]),
    );
  return (
    <section aria-labelledby="policy-heading" className="space-y-5">
      <h2 id="policy-heading" className="text-sm font-semibold">
        Approved models and role policy
      </h2>
      <ul
        data-field="approved-models"
        className="grid gap-3.5 text-[13px] md:grid-cols-2 xl:grid-cols-3"
      >
        {models.models.map((model) => (
          <li
            key={model.profile}
            data-approved-model={model.profile}
            className={cn(
              "border-border min-w-0 rounded-xl border px-[18px] py-4 leading-relaxed",
              model.offered ? "bg-card text-card-foreground" : "bg-background",
            )}
          >
            <span className="font-mono text-[12.5px] wrap-anywhere">
              {modelLabel(model.canonical_id, model.wire_id)}
            </span>
            {model.available ? "" : ". Not in the catalog right now."}
            {model.offered
              ? ""
              : ". Approved, and not offered for new runs until it's qualified."}
          </li>
        ))}
      </ul>
      <RoleEffect state={state} />
      {savedChoiceNotOffered ? (
        <p
          data-field="not-offered"
          role="alert"
          className="border-destructive/40 dark:bg-destructive/10 flex gap-3 rounded-lg border px-3.5 py-3 text-[13.5px] font-medium"
        >
          <TriangleAlert
            aria-hidden="true"
            className="text-destructive mt-0.5 size-4 shrink-0"
          />
          <span>
            A saved choice here names a model that isn&apos;t offered for new
            runs, so new runs are refused until you change it. Nothing replaces
            it for you.
          </span>
        </p>
      ) : null}
      <form onSubmit={(event) => void save(event)} className="space-y-5">
        <div className="border-border border-b">
          <div className={ROW}>
            <label
              htmlFor="workspace-default"
              className="min-w-0 text-[13.5px] font-medium"
            >
              Workspace default
            </label>
            <div className={cn(ROW_CONTROL, "w-44 sm:w-80")}>
              <Select
                id="workspace-default"
                value={defaultProfile}
                onChange={(event) => setDefaultProfile(event.target.value)}
              >
                {choices(defaultProfile).map((model) => (
                  <option
                    key={model.profile}
                    value={model.profile}
                    disabled={!model.offered}
                  >
                    {model.canonical_id}
                  </option>
                ))}
              </Select>
            </div>
          </div>
        </div>
        <fieldset className="min-w-0">
          <legend className="mb-2 text-sm font-semibold">Role overrides</legend>
          <div className="border-border grid gap-x-8 border-b md:grid-cols-2">
            {state.policy.bindings.map((binding) => (
              <div key={binding.role} className={ROW}>
                <label
                  htmlFor={`role-${binding.role}`}
                  className="min-w-0 font-mono text-[12.5px] break-all"
                >
                  {binding.role}
                </label>
                <div className={ROW_CONTROL}>
                  <Select
                    id={`role-${binding.role}`}
                    value={overrides[binding.role] ?? WORKSPACE_DEFAULT}
                    onChange={(event) => {
                      const next = { ...overrides };
                      if (event.target.value === WORKSPACE_DEFAULT) {
                        delete next[binding.role];
                      } else {
                        next[binding.role] = event.target.value;
                      }
                      setOverrides(next);
                    }}
                  >
                    <option value={WORKSPACE_DEFAULT}>Workspace default</option>
                    {choices(overrides[binding.role]).map((model) => (
                      <option
                        key={model.profile}
                        value={model.profile}
                        disabled={!model.offered}
                      >
                        {model.canonical_id}
                      </option>
                    ))}
                  </Select>
                </div>
              </div>
            ))}
          </div>
        </fieldset>
        <div className="border-border border-t pt-4">
          <Button type="submit" size="lg" disabled={busy}>
            {busy ? "Saving" : "Save policy"}
          </Button>
        </div>
      </form>
      {message === null ? null : (
        <p
          role="status"
          data-policy-message="true"
          aria-live="polite"
          className="text-sm font-medium"
        >
          {message}
        </p>
      )}
    </section>
  );
}
