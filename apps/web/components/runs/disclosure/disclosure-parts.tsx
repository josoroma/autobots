import type { ModelList } from "@autobots/api-client";
import { Info, Lock, Send, TriangleAlert } from "lucide-react";

import { Eyebrow } from "@/components/ui/eyebrow";
import { Select } from "@/components/ui/field";
import { formatUsd } from "@/lib/format";
import { summarizerDiffers } from "@/lib/model-roles";
import {
  WORKSPACE_DEFAULT,
  type Binding,
  type Disclosure,
} from "@/lib/runs/disclosure";
import { cn } from "@/lib/utils";

// Each sentence below keeps its exact words, which product rules and tests read. Spans only arrange
// them: a small label, the figure, and hidden punctuation that keeps the sentence whole.
// Decision 0021: quiet hairlines, no filled tiles, so the same block reads well in every screen that
// starts a run. Light surfaces stay unfilled, as muted text on a light tint measures under 4.5:1.

/** A run-wide model choice, from the models offered for new runs. */
export function ModelChoice({
  models,
  chosen,
  onChoose,
}: {
  models: ModelList;
  chosen: string;
  onChoose: (profile: string) => void;
}) {
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
      <label htmlFor="run-model" className="font-medium">
        Model for this run
      </label>
      <Select
        id="run-model"
        value={chosen}
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
  );
}

/** Why the model isn't shown: it can't be read, it's still loading, or it isn't offered. */
export function DisclosureNotice({
  failed,
  shown,
}: {
  failed: boolean;
  shown: Disclosure;
}) {
  if (failed)
    return (
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
    );
  if (shown.executor === null)
    return (
      <p className="text-muted-foreground">Loading what this run would use.</p>
    );
  if (!shown.refused) return null;
  return (
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
        {shown.fromExpert
          ? "It's in this Expert's saved version, so settings won't change it. Save a new revision of the Expert, without it, and start a new session."
          : "Change it in settings."}
      </span>
    </p>
  );
}

/** The executor's model once it's shown, where it runs, and the run's budget. */
export function ModelAndBudget({
  model,
  budgetMicroUsd,
  local = false,
}: {
  model: string | null;
  budgetMicroUsd: number;
  local?: boolean;
}) {
  return (
    <div
      className={cn(
        "grid rounded-lg border",
        model !== null && "divide-y sm:grid-cols-2 sm:divide-x sm:divide-y-0",
      )}
    >
      {model === null ? null : (
        <p
          data-disclosure="model"
          className="flex min-w-0 flex-col gap-0.5 px-3.5 py-2.5"
        >
          <Eyebrow>
            Model<span className="sr-only">:</span>
          </Eyebrow>{" "}
          <span className="font-medium wrap-anywhere">{model}</span>
          <span className="sr-only">,</span>{" "}
          <span className="text-muted-foreground">
            {local ? "served on this Mac." : "through OpenRouter."}
          </span>
        </p>
      )}
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
  );
}

/** Every role's model, of which only the executor dispatches, and the summarizer's note. */
export function RoleDetails({
  bindings,
  canonical,
}: {
  bindings: readonly Binding[];
  canonical: (profile: string) => string;
}) {
  return (
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
            The summarizer differs from the executor, so this run would pause
            with route_not_bound if it needs compaction, and resuming
            wouldn&apos;t clear that.
          </span>
        </p>
      ) : null}
    </>
  );
}

/** Where model calls go and what they carry, and that nothing is sent until Run is pressed. On
 * Local, nothing goes to OpenRouter, but tool calls still leave the Mac (Decision 0041 A13). */
export function DataNotice({
  sendsOnlyIfAgent,
  local = false,
}: {
  sendsOnlyIfAgent: boolean;
  local?: boolean;
}) {
  const ifAgent = sendsOnlyIfAgent ? ", if an agent step runs" : "";
  return (
    <div className="flex flex-col gap-1.5 border-t pt-3 text-ui">
      <p
        data-disclosure="data"
        className="text-muted-foreground flex items-start gap-2"
      >
        <Send aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
        {local ? (
          <span>
            Nothing goes to OpenRouter. Sent to the local model on this Mac
            {ifAgent}: selected instructions, conversation and context excerpts,
            retrieved material and tool outputs. Tool calls such as SerpApi,
            Jina and YouTube still leave the Mac. App records stay on this Mac.
          </span>
        ) : (
          <span>
            Sent to OpenRouter
            {ifAgent}: selected instructions, conversation and context excerpts,
            retrieved material, tool outputs and required protocol metadata. App
            records stay on this Mac.
          </span>
        )}
      </p>
      <p
        data-disclosure="consent"
        className="flex items-center gap-2 font-medium"
      >
        <Lock aria-hidden="true" className="size-3.5 shrink-0" />
        <span>Nothing is sent until you press Run.</span>
      </p>
    </div>
  );
}
