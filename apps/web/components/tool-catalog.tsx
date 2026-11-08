"use client";

import {
  parseToolCatalog,
  parseToolVersions,
  type ToolCatalog,
  type ToolDescriptor,
  type ToolVersions,
} from "@autobots/api-client";
import {
  Calculator,
  ChartLine,
  Clock,
  Code,
  Compass,
  FileText,
  Globe,
  GraduationCap,
  Link2,
  ListTodo,
  type LucideIcon,
  Network,
  Plug,
  Search,
  ShieldAlert,
  ShieldCheck,
  Users,
  Wallet,
  Wrench,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, IconTile } from "@/components/ui/card";
import { Select } from "@/components/ui/field";
import { cn } from "@/lib/utils";

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

// Decorative: the group heading and the tool's title carry the meaning.
const GROUP_ICONS: Record<string, LucideIcon> = {
  planning: ListTodo,
  general: Calculator,
  web_search: Search,
  web_extraction: Link2,
  web_crawling: Network,
  files: FileText,
  market_data: ChartLine,
  browsing: Compass,
  code: Code,
  connectors: Plug,
  delegation: Users,
  learning: GraduationCap,
};

function Availability({ tool }: { tool: ToolDescriptor }) {
  const available = tool.availability === "available";
  return (
    <Badge
      variant={available ? "success" : "muted"}
      dot={available}
      data-availability={tool.availability}
    >
      {AVAILABILITY[tool.availability] ?? tool.availability}
    </Badge>
  );
}

const TOOLBAR_LABEL =
  "flex w-full flex-col items-stretch gap-1 text-[13px] font-medium sm:w-auto sm:flex-row sm:items-center sm:gap-2 [&>span:first-child]:text-muted-foreground";

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
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
        <form
          aria-label="Filter tools"
          className="flex flex-wrap items-center gap-x-4 gap-y-2"
          onSubmit={(event) => event.preventDefault()}
        >
          <label className={TOOLBAR_LABEL}>
            <span>Group</span>
            <Select
              className="h-8 w-full sm:w-44"
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
          <label className={TOOLBAR_LABEL}>
            <span>Availability</span>
            <Select
              className="h-8 w-full sm:w-52"
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
          <label className={TOOLBAR_LABEL}>
            <span>Provider</span>
            <Select
              className="h-8 w-full sm:w-48"
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
        <p
          className="text-muted-foreground text-[12.5px] sm:ml-auto"
          data-field="digest"
        >
          {shown.length} of {catalog.tools.length} tools. Catalog{" "}
          <code className="font-mono">
            {catalog.catalog_digest.slice(0, 12)}
          </code>
          .
        </p>
      </div>
      {catalog.groups
        .filter((item) => shown.some((tool) => tool.group === item.group))
        .map((item) => {
          const Icon = GROUP_ICONS[item.group] ?? Wrench;
          return (
            <section
              key={item.group}
              aria-labelledby={`group-${item.group}`}
              data-group={item.group}
            >
              <div className="mb-1 flex flex-wrap items-baseline gap-x-2.5 gap-y-0.5">
                <h2
                  id={`group-${item.group}`}
                  className="text-[13.5px] font-semibold"
                >
                  {item.title}
                </h2>
                <p className="text-muted-foreground text-[12.5px]">
                  {item.description}
                </p>
              </div>
              <ul>
                {shown
                  .filter((tool) => tool.group === item.group)
                  .map((tool) => {
                    const fix = repair(tool);
                    return (
                      <li
                        key={tool.tool_id}
                        data-tool={tool.tool_id}
                        className="border-border grid grid-cols-[30px_minmax(0,1fr)] items-start gap-x-3 gap-y-2 border-t px-3 py-2.5 sm:grid-cols-[30px_minmax(0,1fr)_auto]"
                      >
                        <IconTile
                          icon={Icon}
                          className="mt-0.5 size-[30px] rounded-lg"
                        />
                        <div className="min-w-0 space-y-1">
                          <Link
                            href={`/tools/${encodeURIComponent(tool.tool_id)}`}
                            className="text-[13.5px] font-semibold underline-offset-4 hover:underline"
                          >
                            {tool.title}
                          </Link>
                          <p className="text-muted-foreground flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs">
                            <code className="font-mono text-[11.5px]">
                              {tool.tool_id} v{tool.version}
                            </code>
                            <span>
                              · {PROVIDERS[tool.provider] ?? tool.provider} ·{" "}
                              {CLASSES[tool.operation_class] ??
                                tool.operation_class}{" "}
                              ·{" "}
                              {tool.network
                                ? "Leaves this Mac"
                                : "Stays on this Mac"}{" "}
                              · {COSTS[tool.cost_class] ?? tool.cost_class}
                            </span>
                          </p>
                          <p className="text-[13px] leading-relaxed">
                            {tool.description}
                          </p>
                          {fix === null ? null : (
                            <p className="text-[13px]" data-field="repair">
                              {fix}
                            </p>
                          )}
                        </div>
                        <div className="col-start-2 flex flex-wrap items-center gap-1.5 sm:col-start-3 sm:flex-col sm:items-end">
                          <Availability tool={tool} />
                          {tool.approval === "always" ? (
                            <Badge variant="attention">
                              <ShieldAlert aria-hidden="true" />
                              Every call waits for a person
                            </Badge>
                          ) : null}
                        </div>
                      </li>
                    );
                  })}
              </ul>
            </section>
          );
        })}
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
      <h2 id={id} className="text-sm font-semibold">
        {title}
      </h2>
      {fields.length === 0 ? (
        <p className="text-muted-foreground text-sm">None.</p>
      ) : (
        <div className="overflow-x-auto">
          <table
            className="w-full text-left text-[13px]"
            data-fields={direction}
          >
            <caption className="sr-only">
              {title} of {tool.title}
            </caption>
            <thead>
              <tr className="text-muted-foreground border-b text-xs">
                <th scope="col" className="pr-3 pb-2 font-medium">
                  Field
                </th>
                <th scope="col" className="pr-3 pb-2 font-medium">
                  Type
                </th>
                <th scope="col" className="pr-3 pb-2 font-medium">
                  Required
                </th>
                <th scope="col" className="pr-3 pb-2 font-medium">
                  Constraints
                </th>
                <th scope="col" className="pr-3 pb-2 font-medium">
                  On run screens
                </th>
              </tr>
            </thead>
            <tbody>
              {fields.map((field) => (
                <tr
                  key={field.path}
                  data-field-path={field.path}
                  className="border-b align-top last:border-b-0"
                >
                  <th scope="row" className="py-2 pr-3 font-normal">
                    <code className="font-mono text-[12.5px]">
                      {field.path}
                    </code>
                    {field.description ? (
                      <span className="text-muted-foreground block text-xs">
                        {field.description}
                      </span>
                    ) : null}
                  </th>
                  <td className="py-2 pr-3">
                    <code className="font-mono text-[12.5px]">
                      {field.type}
                    </code>
                  </td>
                  <td className="py-2 pr-3">
                    {field.required ? "Required" : "Optional"}
                  </td>
                  <td className="py-2 pr-3">
                    {Object.keys(field.constraints).length === 0
                      ? "None"
                      : Object.entries(field.constraints)
                          .map(
                            ([key, value]) => `${key} ${JSON.stringify(value)}`,
                          )
                          .join(", ")}
                  </td>
                  <td className="py-2 pr-3">
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
  const Icon = GROUP_ICONS[tool.group] ?? Wrench;
  const approval = tool.approval === "always";
  return (
    <div className="space-y-5">
      <Card aria-labelledby="tool-heading" className="space-y-5">
        <div className="space-y-3">
          <div className="flex items-start gap-3">
            <IconTile icon={Icon} className="size-[34px]" />
            <div className="ml-auto">
              <Availability tool={tool} />
            </div>
          </div>
          <h2
            id="tool-heading"
            className="font-serif text-[22px] leading-tight font-normal tracking-[-0.015em]"
          >
            {tool.title}
          </h2>
          <p className="text-muted-foreground text-[13.5px] leading-relaxed">
            {tool.description}
          </p>
          {fix === null ? null : (
            <p className="text-sm" data-field="repair">
              {fix}
            </p>
          )}
        </div>
        <dl className="grid gap-2 sm:grid-cols-2">
          <Fact icon={Globe} term="Network">
            {tool.network ? "Leaves this Mac" : "Stays on this Mac"}
          </Fact>
          <Fact icon={Wallet} term="Cost">
            {COSTS[tool.cost_class] ?? tool.cost_class}
            {tool.cost_note ? `, ${tool.cost_note}` : ""}
          </Fact>
          <Fact
            icon={approval ? ShieldAlert : ShieldCheck}
            term="Approval"
            className={approval ? "text-attention font-medium" : undefined}
          >
            {approval ? "Every call waits for a person" : "Not needed"}
          </Fact>
          <Fact icon={Clock} term="Limits">
            {tool.limits
              ? `${tool.limits.timeout_seconds} s, ${tool.limits.retries} retries, ${tool.limits.max_output_bytes} output bytes`
              : "Not registered"}
          </Fact>
        </dl>
        <dl className="grid grid-cols-[7rem_minmax(0,1fr)] items-center gap-x-3 gap-y-2.5 border-t pt-4 text-[13px]">
          <dt className="text-muted-foreground">ID</dt>
          <dd>
            <code className="border-border rounded-md border px-1.5 py-0.5 font-mono text-[12px]">
              {tool.tool_id}
            </code>
          </dd>
          <dt className="text-muted-foreground">Version</dt>
          <dd>
            <label className="sr-only" htmlFor="tool-version">
              Version
            </label>
            <Select
              id="tool-version"
              className="h-8 w-full max-w-40"
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
          <dt className="text-muted-foreground">Provider</dt>
          <dd>{PROVIDERS[tool.provider] ?? tool.provider}</dd>
          <dt className="text-muted-foreground">Class</dt>
          <dd>{CLASSES[tool.operation_class] ?? tool.operation_class}</dd>
          <dt className="text-muted-foreground">Key</dt>
          <dd data-field="key" className="break-words">
            {tool.key_requirement
              ? `${tool.key_requirement.variables.join(", ")}, from the worker's environment`
              : "None"}
          </dd>
        </dl>
        <dl className="space-y-2 border-t pt-4">
          <dt className="text-muted-foreground text-xs font-semibold tracking-wide">
            Granted to
          </dt>
          <dd>
            {tool.grantable_to.length === 0 ? (
              <span className="text-sm">Nothing can grant it</span>
            ) : (
              <ul className="flex flex-wrap gap-2">
                {tool.grantable_to.map((item) => (
                  <li
                    key={item}
                    className="border-border rounded-full border px-2.5 py-0.5 text-[12.5px]"
                  >
                    {item.replaceAll("_", " ")}
                  </li>
                ))}
              </ul>
            )}
          </dd>
        </dl>
      </Card>
      <FieldTable tool={tool} direction="input" />
      <FieldTable tool={tool} direction="output" />
      <details className="text-sm">
        <summary className="cursor-pointer font-semibold">JSON Schema</summary>
        <pre className="border-border bg-background mt-2 overflow-x-auto rounded-lg border px-3.5 py-3 font-mono text-xs leading-relaxed">
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

function Fact({
  icon: Icon,
  term,
  className,
  children,
}: {
  icon: LucideIcon;
  term: string;
  className?: string | undefined;
  children: ReactNode;
}) {
  return (
    <div className="border-border bg-background rounded-lg border px-3 py-2.5 text-[13px]">
      <dt className="text-muted-foreground mb-0.5 flex items-center gap-1.5 text-[11.5px]">
        <Icon aria-hidden="true" className="size-3.5 shrink-0" />
        {term}
      </dt>
      <dd className={cn(className)}>{children}</dd>
    </div>
  );
}
