import type { ModelAvailability, ModelList } from "@autobots/api-client";

import { fetchedAt, modelLabel, perMillion } from "@/lib/model-policy";
import { cn } from "@/lib/utils";

function Capabilities({ names }: { names: readonly string[] }) {
  if (names.length === 0) {
    return <span className="text-muted-foreground">None listed.</span>;
  }
  return (
    <ul className="flex flex-wrap gap-1.5">
      {names.map((name) => (
        <li
          key={name}
          data-capability={name}
          className="border-border rounded-full border px-2 py-0.5 font-mono text-[11.5px]"
        >
          {name}
        </li>
      ))}
    </ul>
  );
}

// Prices and capabilities from the catalog. A route's qualification is recorded under the provider.
function CatalogFacts({ model }: { model: ModelAvailability }) {
  return (
    <dl
      data-field="catalog-facts"
      className="border-border mt-3 space-y-1.5 border-t pt-3"
    >
      <div className="flex gap-2">
        <dt className="text-muted-foreground">Input</dt>
        <dd data-price="input" className="ml-auto tabular-nums">
          {perMillion(model.input_per_million_micro_usd)} per 1M tokens
        </dd>
      </div>
      <div className="flex gap-2">
        <dt className="text-muted-foreground">Output</dt>
        <dd data-price="output" className="ml-auto tabular-nums">
          {perMillion(model.output_per_million_micro_usd)} per 1M tokens
        </dd>
      </div>
      <div>
        <dt className="text-muted-foreground">
          Capabilities, from the catalog
        </dt>
        <dd data-field="capabilities" className="mt-1">
          <Capabilities names={model.capabilities} />
        </dd>
      </div>
    </dl>
  );
}

function ApprovedModelCard({ model }: { model: ModelAvailability }) {
  return (
    <li
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
      <CatalogFacts model={model} />
    </li>
  );
}

/** PRD-Studio MD-01: each approved profile with its catalog facts, and when the catalog was read. */
export function ApprovedModels({ models }: { models: ModelList }) {
  return (
    <>
      <ul
        data-field="approved-models"
        className="grid gap-3.5 text-[13px] md:grid-cols-2 xl:grid-cols-3"
      >
        {models.models.map((model) => (
          <ApprovedModelCard key={model.profile} model={model} />
        ))}
      </ul>
      <p
        data-field="catalog-fetched"
        className="text-muted-foreground text-[12.5px]"
      >
        {fetchedAt(models.fetched_at)} Prices and capabilities come from the
        catalog. Whether a route is qualified is recorded separately, under the
        provider.
      </p>
    </>
  );
}
