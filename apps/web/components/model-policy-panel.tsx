"use client";

import {
  parseModelList,
  parseModelPolicyState,
  type ModelList,
  type ModelPolicyState,
} from "@autobots/api-client";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Select } from "@/components/ui/field";
import { csrfFetch } from "@/lib/csrf-fetch";

const WORKSPACE_DEFAULT = "";
const EXECUTOR = "executor";
const SUMMARIZER = "summarizer";

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
    <div data-field="role-effect" className="space-y-1 text-sm">
      <p>
        Only the executor&apos;s binding dispatches in this release. Other roles
        that differ from it don&apos;t take effect.
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
        A summarizer that differs pauses the run with route_not_bound, once the
        run needs compaction.
      </p>
      {differing.some((binding) => binding.role === SUMMARIZER) ? (
        <p data-role-effect="summarizer" className="font-medium">
          The summarizer differs here, so long runs will pause that way.
        </p>
      ) : null}
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
  return (
    <Card aria-labelledby="policy-heading" className="space-y-4">
      <h2 id="policy-heading" className="text-lg font-medium">
        Approved models and role policy
      </h2>
      <ul data-field="approved-models" className="space-y-1 text-sm">
        {models.models.map((model) => (
          <li key={model.profile} data-approved-model={model.profile}>
            <span className="break-all">
              {modelLabel(model.canonical_id, model.wire_id)}
            </span>
            {model.available ? "" : ". Not in the catalog right now."}
          </li>
        ))}
      </ul>
      <RoleEffect state={state} />
      <form onSubmit={(event) => void save(event)} className="space-y-3">
        <div className="space-y-1">
          <label htmlFor="workspace-default" className="text-sm font-medium">
            Workspace default
          </label>
          <Select
            id="workspace-default"
            value={defaultProfile}
            onChange={(event) => setDefaultProfile(event.target.value)}
          >
            {models.models.map((model) => (
              <option key={model.profile} value={model.profile}>
                {model.canonical_id}
              </option>
            ))}
          </Select>
        </div>
        <fieldset className="space-y-2">
          <legend className="text-sm font-medium">Role overrides</legend>
          {state.policy.bindings.map((binding) => (
            <div key={binding.role} className="space-y-1">
              <label
                htmlFor={`role-${binding.role}`}
                className="text-muted-foreground text-sm"
              >
                {binding.role}
              </label>
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
                {models.models.map((model) => (
                  <option key={model.profile} value={model.profile}>
                    {model.canonical_id}
                  </option>
                ))}
              </Select>
            </div>
          ))}
        </fieldset>
        <Button type="submit" disabled={busy}>
          {busy ? "Saving" : "Save policy"}
        </Button>
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
    </Card>
  );
}
