"use client";

import {
  parseModelList,
  parseModelPolicyState,
  type ModelList,
  type ModelPolicyState,
} from "@autobots/api-client";
import { Info, Lock, Send, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";

import { Eyebrow } from "@/components/ui/eyebrow";
import { Select } from "@/components/ui/field";
import { FALLBACK_BUDGET_MICRO_USD } from "@/lib/budget";
import { formatUsd } from "@/lib/format";
import { summarizerDiffers } from "@/lib/model-roles";
import { cn } from "@/lib/utils";

// MP-07. Every screen that creates a run shows this, and reading it starts nothing.
const EXECUTOR = "executor";
const WORKSPACE_DEFAULT = "";

export function RunDisclosure({
  chosen,
  onChoose,
  roleOverrides,
  // A screen that sends no budget runs with RunRequest's default limit, US$1.00 as D11's default is.
  budgetMicroUsd = FALLBACK_BUDGET_MICRO_USD,
  sendsOnlyIfAgent = false,
  usesModel = true,
}: {
  // Absent where a screen offers no per-run choice.
  chosen?: string;
  onChoose?: (profile: string) => void;
  // An Expert's own role bindings, which a run-wide choice doesn't replace.
  roleOverrides?: Readonly<Record<string, unknown>> | undefined;
  budgetMicroUsd?: number;
  sendsOnlyIfAgent?: boolean;
  // False for a workflow version with no agent step, which calls no model and isn't refused.
  usesModel?: boolean;
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
  // The server's own rule: any binding that isn't offered refuses the whole run.
  const notOffered = (profile: unknown): boolean =>
    models?.models.find((model) => model.profile === profile)?.offered ===
    false;
  const refused =
    usesModel && bindings.some((binding) => notOffered(binding.profile));
  // An Expert's binding outranks the workspace and a run's own choice, and a session pins its version.
  const fromExpert = Object.values(roleOverrides ?? {}).some(notOffered);
  // The model, roles and summarizer note appear only once the choice is read and allowed.
  const showModel = !failed && executor !== undefined && !refused;

  // Each sentence below keeps its exact words, which product rules and tests read. Spans only arrange
  // them: a small label, the figure, and hidden punctuation that keeps the sentence whole.
  // Decision 0021: quiet hairlines, no filled tiles, so the same block reads well in every screen that
  // starts a run. Light surfaces stay unfilled, as muted text on a light tint measures under 4.5:1.
  return (
    <div data-field="disclosure" className="flex flex-col gap-3 text-sm">
      {onChoose === undefined || models === null ? null : (
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
          <label htmlFor="run-model" className="font-medium">
            Model for this run
          </label>
          <Select
            id="run-model"
            value={chosenProfile}
            onChange={(event) => onChoose(event.target.value)}
            className="sm:w-72"
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
        <p
          data-disclosure="models-unavailable"
          className="flex items-start gap-2.5 rounded-lg border px-3.5 py-3"
        >
          <Info
            aria-hidden="true"
            className="text-muted-foreground mt-0.5 size-4 shrink-0"
          />
          <span>
            The models this run would use can&apos;t be read right now. It would
            use the workspace setting, as Settings shows it.
          </span>
        </p>
      ) : executor === undefined ? (
        <p className="text-muted-foreground">
          Loading what this run would use.
        </p>
      ) : refused ? (
        <p
          data-disclosure="not-offered"
          role="alert"
          className="border-destructive/50 dark:bg-destructive/10 flex items-start gap-2.5 rounded-lg border px-3.5 py-3"
        >
          <TriangleAlert
            aria-hidden="true"
            className="text-destructive mt-0.5 size-4 shrink-0"
          />
          <span>
            A saved model choice here isn&apos;t offered for new runs until
            it&apos;s qualified, so pressing Run would start nothing.{" "}
            {fromExpert
              ? "It's in this Expert's saved version, so settings won't change it. Save a new revision of the Expert, without it, and start a new session."
              : "Change it in settings."}
          </span>
        </p>
      ) : null}
      <div
        className={cn(
          "grid rounded-lg border",
          showModel && "divide-y sm:grid-cols-2 sm:divide-x sm:divide-y-0",
        )}
      >
        {showModel && executor !== undefined ? (
          <p
            data-disclosure="model"
            className="flex min-w-0 flex-col gap-0.5 px-3.5 py-2.5"
          >
            <Eyebrow>
              Model<span className="sr-only">:</span>
            </Eyebrow>{" "}
            <span className="font-medium wrap-anywhere">
              {canonical(executor.profile)}
            </span>
            <span className="sr-only">,</span>{" "}
            <span className="text-muted-foreground">through OpenRouter.</span>
          </p>
        ) : null}
        <p
          data-disclosure="budget"
          className="flex min-w-0 flex-col gap-0.5 px-3.5 py-2.5"
        >
          <Eyebrow>
            Budget<span className="sr-only">:</span>
          </Eyebrow>{" "}
          <span>
            <span className="text-muted-foreground">up to</span>{" "}
            <span className="font-medium tabular-nums">
              {formatUsd(budgetMicroUsd)}
            </span>
          </span>{" "}
          <span className="text-muted-foreground">for this run.</span>
        </p>
      </div>
      {showModel ? (
        <>
          <details className="rounded-lg border px-3.5 py-2.5">
            <summary className="cursor-pointer font-medium">
              Roles, of which only the executor dispatches
            </summary>
            <ul
              data-disclosure="roles"
              className="mt-2 space-y-1 border-t pt-2 font-mono text-xs"
            >
              {bindings.map((binding) => (
                <li key={binding.role} className="wrap-anywhere">
                  {binding.role}: {canonical(binding.profile)}
                </li>
              ))}
            </ul>
          </details>
          {summarizerDiffers(bindings) ? (
            <p data-disclosure="summarizer" className="flex items-start gap-2">
              <TriangleAlert
                aria-hidden="true"
                className="mt-0.5 size-4 shrink-0"
              />
              <span>
                The summarizer differs from the executor, so this run would
                pause with route_not_bound if it needs compaction, and resuming
                wouldn&apos;t clear that.
              </span>
            </p>
          ) : null}
        </>
      ) : null}
      <div className="flex flex-col gap-1.5 border-t pt-3 text-[13px]">
        <p
          data-disclosure="data"
          className="text-muted-foreground flex items-start gap-2"
        >
          <Send aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
          <span>
            Sent to OpenRouter
            {sendsOnlyIfAgent ? ", if an agent step runs" : ""}: selected
            instructions, conversation and context excerpts, retrieved material,
            tool outputs and required protocol metadata. App records stay on
            this Mac.
          </span>
        </p>
        <p
          data-disclosure="consent"
          className="flex items-center gap-2 font-medium"
        >
          <Lock aria-hidden="true" className="size-3.5 shrink-0" />
          <span>Nothing is sent until you press Run.</span>
        </p>
      </div>
    </div>
  );
}
