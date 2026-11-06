"use client";

import {
  parseModelList,
  parseModelPolicyState,
  type ModelList,
  type ModelPolicyState,
} from "@autobots/api-client";
import { useEffect, useState } from "react";
import { Select } from "@/components/ui/field";

// MP-07. Every screen that creates a run shows this, and reading it starts nothing.
const EXECUTOR = "executor";
const WORKSPACE_DEFAULT = "";
const MICRO_USD = 1_000_000;
export const DEFAULT_BUDGET_MICRO_USD = 1_000_000;

export function RunDisclosure({
  chosen,
  onChoose,
  roleOverrides,
  budgetMicroUsd = DEFAULT_BUDGET_MICRO_USD,
  sendsOnlyIfAgent = false,
}: {
  // Absent where a screen offers no per-run choice.
  chosen?: string;
  onChoose?: (profile: string) => void;
  // An Expert's own role bindings, which a run-wide choice doesn't replace.
  roleOverrides?: Readonly<Record<string, unknown>> | undefined;
  budgetMicroUsd?: number;
  sendsOnlyIfAgent?: boolean;
}) {
  const [models, setModels] = useState<ModelList | null>(null);
  const [policy, setPolicy] = useState<ModelPolicyState | null>(null);
  const [failed, setFailed] = useState(false);

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
        setPolicy(parseModelPolicyState(await policyReply.json()));
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
    };
  }, []);

  const canonical = (profile: string): string =>
    models?.models.find((model) => model.profile === profile)?.canonical_id ??
    profile;
  const chosenProfile = chosen ?? WORKSPACE_DEFAULT;
  const bindings = (policy?.policy.bindings ?? []).map((binding) => {
    const expert = roleOverrides?.[binding.role];
    return {
      role: binding.role,
      profile:
        typeof expert === "string"
          ? expert
          : chosenProfile !== WORKSPACE_DEFAULT
            ? chosenProfile
            : binding.profile,
    };
  });
  const executor = bindings.find((binding) => binding.role === EXECUTOR);

  return (
    <div
      data-field="disclosure"
      className="bg-muted space-y-2 rounded-md p-3 text-sm"
    >
      {onChoose === undefined || models === null ? null : (
        <div className="space-y-1">
          <label htmlFor="run-model" className="font-medium">
            Model for this run
          </label>
          <Select
            id="run-model"
            value={chosenProfile}
            onChange={(event) => onChoose(event.target.value)}
          >
            <option value={WORKSPACE_DEFAULT}>The workspace setting</option>
            {models.models
              .filter((model) => model.offered)
              .map((model) => (
                <option key={model.profile} value={model.profile}>
                  {model.canonical_id}
                </option>
              ))}
          </Select>
        </div>
      )}
      {failed ? (
        <p data-disclosure="models-unavailable">
          The models this run would use can&apos;t be read right now. It would
          use the workspace setting, as Settings shows it.
        </p>
      ) : executor === undefined ? (
        <p>Loading what this run would use.</p>
      ) : (
        <>
          <p data-disclosure="model">
            Model: {canonical(executor.profile)}, through OpenRouter.
          </p>
          <details>
            <summary>Roles, of which only the executor dispatches</summary>
            <ul data-disclosure="roles" className="mt-1 space-y-1">
              {bindings.map((binding) => (
                <li key={binding.role}>
                  {binding.role}: {canonical(binding.profile)}
                </li>
              ))}
            </ul>
          </details>
          {bindings.find((binding) => binding.role === "summarizer")
            ?.profile !== executor.profile ? (
            <p data-disclosure="summarizer">
              The summarizer differs from the executor, so this run would pause
              with route_not_bound if it needs compaction, and resuming
              wouldn&apos;t clear that.
            </p>
          ) : null}
        </>
      )}
      <p data-disclosure="budget">
        Budget: up to US${(budgetMicroUsd / MICRO_USD).toFixed(2)} for this run.
      </p>
      <p data-disclosure="data">
        Sent to OpenRouter{sendsOnlyIfAgent ? ", if an agent step runs" : ""}:
        selected instructions, conversation and context excerpts, retrieved
        material, tool outputs and required protocol metadata. App records stay
        on this Mac.
      </p>
      <p data-disclosure="consent">Nothing is sent until you press Run.</p>
    </div>
  );
}
