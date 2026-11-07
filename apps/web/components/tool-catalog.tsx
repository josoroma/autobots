"use client";

import {
  parseToolCatalog,
  parseToolVersions,
  type ToolCatalog,
  type ToolDescriptor,
  type ToolVersions,
} from "@autobots/api-client";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Select } from "@/components/ui/field";

// PRD-Tool-Catalog TS-01 to TS-03. Every state is said in words; a badge never stands for one alone.

const PROVIDERS: Record<string, string> = {
  autobots: "Autobots, on this Mac",
  tavily: "Tavily",
  jina: "Jina",
  yahoo_finance: "Yahoo Finance",
  world_bank: "World Bank",
  github: "GitHub",
};

const CLASSES: Record<string, string> = {
  pure: "Pure",
  read_only: "Read only",
  reversible_internal_write: "Writes inside the run",
  consequential_external_write: "Changes something outside",
  arbitrary_execution: "Arbitrary execution",
};

const COSTS: Record<string, string> = {
  free_local: "No provider charge",
  metered_provider: "Metered by its provider",
};

export const AVAILABILITY: Record<string, string> = {
  available: "Available",
  key_missing: "Unavailable: key not set",
  disabled_by_policy: "Unavailable: disabled by policy",
  not_qualified: "Unavailable: not qualified",
};

const AVAILABILITY_FILTERS = ["available", "key_missing", "disabled_by_policy"];

export function repair(tool: ToolDescriptor): string | null {
  if (tool.availability === "key_missing" && tool.key_requirement) {
    const names = tool.key_requirement.variables.join(" and ");
    return `Set ${names} in the worker's environment, then restart the worker and the API.`;
  }
  if (tool.availability_reason === "isolated_executor_not_qualified") {
    return "Disabled until the isolated browser executor is qualified and turned on. See the operations runbook.";
  }
  if (tool.availability === "not_qualified") {
    return "Waits for its provider's qualification.";
  }
  return null;
}

function Availability({ tool }: { tool: ToolDescriptor }) {
  return (
    <Badge
      variant={tool.availability === "available" ? "secondary" : "outline"}
      data-availability={tool.availability}
    >
      {AVAILABILITY[tool.availability] ?? tool.availability}
    </Badge>
  );
}

function useLoaded<T>(path: string, parse: (value: unknown) => T) {
  const [state, setState] = useState<
    { kind: "loading" } | { kind: "unavailable" } | { kind: "ready"; value: T }
  >({ kind: "loading" });
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    fetch(path, { cache: "no-store", signal: controller.signal })
      .then(async (reply) => {
        if (!active) return;
        if (!reply.ok) {
          setState({ kind: "unavailable" });
          return;
        }
        setState({ kind: "ready", value: parse(await reply.json()) });
      })
      .catch(() => {
        if (active) setState({ kind: "unavailable" });
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [path, parse]);
  return state;
}

export function ToolCatalogPanel() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const group = params.get("group") ?? "";
  const availability = params.get("availability") ?? "";
  const provider = params.get("provider") ?? "";
  const state = useLoaded("/api/v1/tools", parseToolCatalog);

  function choose(name: string, value: string): void {
    const next = new URLSearchParams(params.toString());
    if (value === "") next.delete(name);
    else next.set(name, value);
    const query = next.toString();
    router.replace(query === "" ? pathname : `${pathname}?${query}`);
  }

  if (state.kind === "unavailable") {
    return (
      <p role="alert" data-state="unavailable" className="text-sm">
        The tool catalog isn&apos;t available. Check that the local service is
        running.
      </p>
    );
  }
  if (state.kind === "loading") {
    return (
      <p role="status" className="text-sm">
        Loading the tool catalog.
      </p>
    );
  }
  const catalog: ToolCatalog = state.value;
  const shown = catalog.tools.filter(
    (tool) =>
      (group === "" || tool.group === group) &&
      (availability === "" || tool.availability === availability) &&
      (provider === "" || tool.provider === provider),
  );
  const providers = [...new Set(catalog.tools.map((tool) => tool.provider))];
  return (
    <div className="space-y-6">
      <form
        aria-label="Filter tools"
        className="grid gap-3 sm:grid-cols-3"
        onSubmit={(event) => event.preventDefault()}
      >
        <label className="space-y-1 text-sm font-medium">
          <span>Group</span>
          <Select
            value={group}
            onChange={(event) => choose("group", event.target.value)}
          >
            <option value="">All groups</option>
            {catalog.groups.map((item) => (
              <option key={item.group} value={item.group}>
                {item.title}
              </option>
            ))}
          </Select>
        </label>
        <label className="space-y-1 text-sm font-medium">
          <span>Availability</span>
          <Select
            value={availability}
            onChange={(event) => choose("availability", event.target.value)}
          >
            <option value="">Any availability</option>
            {AVAILABILITY_FILTERS.map((item) => (
              <option key={item} value={item}>
                {AVAILABILITY[item]}
              </option>
            ))}
          </Select>
        </label>
        <label className="space-y-1 text-sm font-medium">
          <span>Provider</span>
          <Select
            value={provider}
            onChange={(event) => choose("provider", event.target.value)}
          >
            <option value="">All providers</option>
            {providers.map((item) => (
              <option key={item} value={item}>
                {PROVIDERS[item] ?? item}
              </option>
            ))}
          </Select>
        </label>
      </form>
      <p className="text-muted-foreground text-sm" data-field="digest">
        {shown.length} of {catalog.tools.length} tools. Catalog{" "}
        <code>{catalog.catalog_digest.slice(0, 12)}</code>.
      </p>
      {catalog.groups
        .filter((item) => shown.some((tool) => tool.group === item.group))
        .map((item) => (
          <Card
            key={item.group}
            aria-labelledby={`group-${item.group}`}
            data-group={item.group}
            className="space-y-3"
          >
            <div>
              <h2 id={`group-${item.group}`} className="text-lg font-medium">
                {item.title}
              </h2>
              <p className="text-muted-foreground text-sm">
                {item.description}
              </p>
            </div>
            <ul className="divide-border divide-y">
              {shown
                .filter((tool) => tool.group === item.group)
                .map((tool) => (
                  <li
                    key={tool.tool_id}
                    data-tool={tool.tool_id}
                    className="space-y-1.5 py-3"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <Link
                        href={`/tools/${encodeURIComponent(tool.tool_id)}`}
                        className="font-medium underline-offset-4 hover:underline"
                      >
                        {tool.title}
                      </Link>
                      <code className="text-muted-foreground text-xs">
                        {tool.tool_id} v{tool.version}
                      </code>
                      <Availability tool={tool} />
                    </div>
                    <p className="text-sm">{tool.description}</p>
                    <p className="text-muted-foreground text-xs">
                      {PROVIDERS[tool.provider] ?? tool.provider} ·{" "}
                      {CLASSES[tool.operation_class] ?? tool.operation_class} ·{" "}
                      {tool.network ? "Leaves this Mac" : "Stays on this Mac"} ·{" "}
                      {COSTS[tool.cost_class] ?? tool.cost_class}
                    </p>
                    {repair(tool) === null ? null : (
                      <p className="text-sm" data-field="repair">
                        {repair(tool)}
                      </p>
                    )}
                  </li>
                ))}
            </ul>
          </Card>
        ))}
    </div>
  );
}

function FieldTable({
  tool,
  direction,
}: {
  tool: ToolDescriptor;
  direction: "input" | "output";
}) {
  const fields = tool.fields.filter((field) => field.direction === direction);
  const title = direction === "input" ? "Inputs" : "Outputs";
  const id = `${direction}-heading`;
  return (
    <Card aria-labelledby={id} className="space-y-3">
      <h2 id={id} className="text-lg font-medium">
        {title}
      </h2>
      {fields.length === 0 ? (
        <p className="text-sm">None.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm" data-fields={direction}>
            <caption className="sr-only">
              {title} of {tool.title}
            </caption>
            <thead>
              <tr className="border-b">
                <th scope="col" className="py-1.5 pr-3 font-medium">
                  Field
                </th>
                <th scope="col" className="py-1.5 pr-3 font-medium">
                  Type
                </th>
                <th scope="col" className="py-1.5 pr-3 font-medium">
                  Required
                </th>
                <th scope="col" className="py-1.5 pr-3 font-medium">
                  Constraints
                </th>
                <th scope="col" className="py-1.5 pr-3 font-medium">
                  On run screens
                </th>
              </tr>
            </thead>
            <tbody>
              {fields.map((field) => (
                <tr
                  key={field.path}
                  data-field-path={field.path}
                  className="border-b align-top"
                >
                  <th scope="row" className="py-1.5 pr-3 font-normal">
                    <code>{field.path}</code>
                    {field.description ? (
                      <span className="text-muted-foreground block text-xs">
                        {field.description}
                      </span>
                    ) : null}
                  </th>
                  <td className="py-1.5 pr-3">
                    <code>{field.type}</code>
                  </td>
                  <td className="py-1.5 pr-3">
                    {field.required ? "Required" : "Optional"}
                  </td>
                  <td className="py-1.5 pr-3">
                    {Object.keys(field.constraints).length === 0
                      ? "None"
                      : Object.entries(field.constraints)
                          .map(
                            ([key, value]) => `${key} ${JSON.stringify(value)}`,
                          )
                          .join(", ")}
                  </td>
                  <td className="py-1.5 pr-3">
                    {field.public ? "Shown" : "Not shown"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

export function ToolDetail({ toolId }: { toolId: string }) {
  const state = useLoaded(
    `/api/v1/tools/${encodeURIComponent(toolId)}`,
    parseToolVersions,
  );
  const [chosen, setChosen] = useState<number | null>(null);
  if (state.kind === "unavailable") {
    return (
      <p role="alert" data-state="unavailable" className="text-sm">
        That tool isn&apos;t in the catalog.
      </p>
    );
  }
  if (state.kind === "loading") {
    return (
      <p role="status" className="text-sm">
        Loading this tool.
      </p>
    );
  }
  const versions: ToolVersions = state.value;
  const newest = versions.versions.at(-1);
  if (newest === undefined) return null;
  const tool =
    versions.versions.find((item) => item.version === chosen) ?? newest;
  const fix = repair(tool);
  return (
    <div className="space-y-6">
      <Card aria-labelledby="tool-heading" className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <h2 id="tool-heading" className="text-lg font-medium">
            {tool.title}
          </h2>
          <Availability tool={tool} />
        </div>
        <p className="text-sm">{tool.description}</p>
        {fix === null ? null : (
          <p className="text-sm" data-field="repair">
            {fix}
          </p>
        )}
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
          <dt className="font-medium">ID</dt>
          <dd>
            <code>{tool.tool_id}</code>
          </dd>
          <dt className="font-medium">Version</dt>
          <dd>
            <label className="sr-only" htmlFor="tool-version">
              Version
            </label>
            <Select
              id="tool-version"
              value={tool.version}
              onChange={(event) => setChosen(Number(event.target.value))}
            >
              {versions.versions.map((item) => (
                <option key={item.version} value={item.version}>
                  Version {item.version}
                </option>
              ))}
            </Select>
          </dd>
          <dt className="font-medium">Provider</dt>
          <dd>{PROVIDERS[tool.provider] ?? tool.provider}</dd>
          <dt className="font-medium">Class</dt>
          <dd>{CLASSES[tool.operation_class] ?? tool.operation_class}</dd>
          <dt className="font-medium">Network</dt>
          <dd>{tool.network ? "Leaves this Mac" : "Stays on this Mac"}</dd>
          <dt className="font-medium">Cost</dt>
          <dd>
            {COSTS[tool.cost_class] ?? tool.cost_class}
            {tool.cost_note ? `, ${tool.cost_note}` : ""}
          </dd>
          <dt className="font-medium">Approval</dt>
          <dd>
            {tool.approval === "always"
              ? "Every call waits for a person"
              : "Not needed"}
          </dd>
          <dt className="font-medium">Key</dt>
          <dd data-field="key">
            {tool.key_requirement
              ? `${tool.key_requirement.variables.join(", ")}, from the worker's environment`
              : "None"}
          </dd>
          <dt className="font-medium">Limits</dt>
          <dd>
            {tool.limits
              ? `${tool.limits.timeout_seconds} s, ${tool.limits.retries} retries, ${tool.limits.max_output_bytes} output bytes`
              : "Not registered"}
          </dd>
          <dt className="font-medium">Granted to</dt>
          <dd>
            {tool.grantable_to.length === 0
              ? "Nothing can grant it"
              : tool.grantable_to.join(", ").replaceAll("_", " ")}
          </dd>
        </dl>
      </Card>
      <FieldTable tool={tool} direction="input" />
      <FieldTable tool={tool} direction="output" />
      <details className="text-sm">
        <summary className="cursor-pointer font-medium">JSON Schema</summary>
        <pre className="bg-muted mt-2 overflow-x-auto rounded-xl p-3 text-xs">
          {JSON.stringify(
            { input: tool.input_schema, output: tool.output_schema },
            null,
            2,
          )}
        </pre>
      </details>
    </div>
  );
}
