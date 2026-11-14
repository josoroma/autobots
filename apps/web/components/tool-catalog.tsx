"use client";

import {
  parseToolCatalog,
  parseToolGrants,
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
  CalendarClock,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { type ReactNode, useEffect, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, IconTile } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/field";
import { LoadEmpty, LoadState } from "@/components/ui/load-state";
import { useResource } from "@/lib/use-resource";
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

// Decisions 0024 and 0025: these keys can also be saved per workspace in Settings → Keys & vars.
const SAVABLE_KEYS: Record<string, string> = { tavily: "Tavily", jina: "Jina" };

// PK-05: where an available tool's key comes from, never the key.
export function keySource(tool: ToolDescriptor): string | null {
  const requirement = tool.key_requirement;
  if (!requirement) return null;
  const names = requirement.variables.join(", ");
  if (requirement.source === "settings") {
    return "Key saved in Settings → Keys & vars for this workspace";
  }
  if (requirement.source === "environment") {
    return `${names}, from the server environment or .env`;
  }
  return `${names}, not set`;
}

export function repair(tool: ToolDescriptor): string | null {
  if (tool.availability === "key_missing" && tool.key_requirement) {
    const names = tool.key_requirement.variables.join(" and ");
    const savable = SAVABLE_KEYS[tool.key_requirement.credential];
    if (savable !== undefined) {
      return `Save a ${savable} key in Settings → Keys & vars, or set ${names} in .env, then restart the worker and the API.`;
    }
    // PRD-Studio GH-07: names and permissions only, never a value.
    const scopes =
      tool.key_requirement.scopes.length === 0
        ? ""
        : ` The token needs these permissions on that repository only: ${tool.key_requirement.scopes.join(", ")}.`;
    return `Save them in Settings → Keys & vars, or set ${names} in .env.${scopes} After a change to .env, restart the worker and the API.`;
  }
  if (tool.availability_reason === "isolated_executor_not_qualified") {
    return "Disabled until the isolated browser executor is qualified and browsing is turned on in Settings → Keys & vars or .env. See the operations runbook.";
  }
  if (tool.availability === "not_qualified") {
    return "Waits for its provider's qualification.";
  }
  return null;
}

// Decision 0026 C9: `by_action` tools hold only some actions for a person.
const APPROVAL_TEXT: Record<ToolDescriptor["approval"], string> = {
  always: "Every call waits for a person",
  by_action: "Some actions wait for a person",
  never: "Not needed",
};

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
  automation: CalendarClock,
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

export function ToolCatalogPanel() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const group = params.get("group") ?? "";
  const availability = params.get("availability") ?? "";
  const provider = params.get("provider") ?? "";
  const query = (params.get("q") ?? "").trim().toLowerCase();
  const selected = params.get("tool");
  const { state, pending, reload } = useResource(
    "/api/v1/tools",
    parseToolCatalog,
  );

  function choose(name: string, value: string): void {
    const next = new URLSearchParams(params.toString());
    if (value === "") next.delete(name);
    else next.set(name, value);
    const query = next.toString();
    router.replace(query === "" ? pathname : `${pathname}?${query}`);
  }

  if (state.kind !== "ready") {
    return (
      <LoadState
        state={state}
        what="the tool catalog"
        onRetry={reload}
        pending={pending}
      />
    );
  }
  const catalog: ToolCatalog = state.value;
  const shown = catalog.tools.filter(
    (tool) =>
      (group === "" || tool.group === group) &&
      (availability === "" || tool.availability === availability) &&
      (provider === "" || tool.provider === provider) &&
      (query === "" ||
        `${tool.title} ${tool.tool_id} ${tool.description}`
          .toLowerCase()
          .includes(query)),
  );
  // Decision 0026 G2: the detail opens in a modal dialog, and the URL keeps it as ?tool=.
  function panelHref(toolId: string): string {
    const next = new URLSearchParams(params.toString());
    next.set("tool", toolId);
    return `${pathname}?${next.toString()}`;
  }
  function closeHref(): string {
    const next = new URLSearchParams(params.toString());
    next.delete("tool");
    const rest = next.toString();
    return rest === "" ? pathname : `${pathname}?${rest}`;
  }
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
            <span>Search</span>
            <Input
              type="search"
              defaultValue={params.get("q") ?? ""}
              onChange={(event) => choose("q", event.target.value.trim())}
              placeholder="Name, ID or description"
              className="h-8 w-full sm:w-56"
            />
          </label>
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
      <div className="grid gap-6">
        <div className="min-w-0 space-y-5">
          {catalog.groups
            .filter((item) => shown.some((tool) => tool.group === item.group))
            .map((item) => {
              const inGroup = shown.filter((tool) => tool.group === item.group);
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
                    <span
                      data-field="count"
                      className="text-muted-foreground text-[12.5px] tabular-nums"
                    >
                      {inGroup.length} {inGroup.length === 1 ? "tool" : "tools"}
                    </span>
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
                                href={panelHref(tool.tool_id)}
                                scroll={false}
                                aria-current={
                                  selected === tool.tool_id ? "true" : undefined
                                }
                                className="text-[13.5px] font-semibold underline-offset-4 hover:underline"
                              >
                                {tool.title}
                              </Link>
                              <p className="text-muted-foreground flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs">
                                <code className="font-mono text-[11.5px]">
                                  {tool.tool_id} v{tool.version}
                                </code>
                                <span>
                                  · {PROVIDERS[tool.provider] ?? tool.provider}{" "}
                                  ·{" "}
                                  {CLASSES[tool.operation_class] ??
                                    tool.operation_class}{" "}
                                  ·{" "}
                                  {tool.network
                                    ? "Leaves this Mac"
                                    : "Stays on this Mac"}{" "}
                                  · {COSTS[tool.cost_class] ?? tool.cost_class}
                                  {tool.availability === "available" &&
                                  tool.key_requirement?.source
                                    ? ` · Key from ${tool.key_requirement.source === "settings" ? "Settings" : "the environment"}`
                                    : null}
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
                              {tool.approval === "never" ? null : (
                                <Badge variant="attention">
                                  <ShieldAlert aria-hidden="true" />
                                  {APPROVAL_TEXT[tool.approval]}
                                </Badge>
                              )}
                            </div>
                          </li>
                        );
                      })}
                  </ul>
                </section>
              );
            })}
        </div>
        {selected === null ? null : (
          <ToolDialog
            key={selected}
            toolId={selected}
            onClosed={() => {
              router.replace(closeHref(), { scroll: false });
              // Back to the link that opened it, or the list's first link for a deep link.
              const opener = document.querySelector<HTMLAnchorElement>(
                `[data-tool="${CSS.escape(selected)}"] a`,
              );
              opener?.focus();
            }}
          />
        )}
      </div>
    </div>
  );
}

// Decision 0026 G2 and G3: the detail in a native modal dialog, which makes the page behind it inert
// and traps focus. Escape, Close and a click on the backdrop close it, and the URL keeps ?tool=.
function ToolDialog({
  toolId,
  onClosed,
}: {
  toolId: string;
  onClosed: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const element = dialog.current;
    if (element !== null && !element.open) element.showModal();
  }, []);
  return (
    <dialog
      ref={dialog}
      data-panel={toolId}
      aria-labelledby="tool-heading"
      onClose={onClosed}
      onClick={(event) => {
        // The content fills the dialog's box, so a click on the dialog itself is the backdrop.
        if (event.target === event.currentTarget) event.currentTarget.close();
      }}
      className="bg-background text-foreground border-border m-auto max-h-[min(92vh,60rem)] w-[calc(100%-2rem)] max-w-3xl overflow-y-auto overscroll-contain rounded-2xl border p-0 shadow-lg backdrop:bg-black/60"
    >
      <div className="space-y-3 p-5 sm:p-6">
        <div className="flex items-center gap-3 text-[13px]">
          <Link
            href={`/tools/${encodeURIComponent(toolId)}`}
            className="underline underline-offset-4"
          >
            Open as a page
          </Link>
          <form method="dialog" className="ml-auto">
            <Button type="submit" variant="outline" size="sm">
              Close
            </Button>
          </form>
        </div>
        <ToolDetail toolId={toolId} />
      </div>
    </dialog>
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
        // A scroll region a keyboard can reach and screen readers can name (axe scrollable-region-focusable).
        <div
          tabIndex={0}
          role="region"
          aria-label={`${title} table`}
          className="overflow-x-auto"
        >
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
  const { state, pending, reload } = useResource(
    `/api/v1/tools/${encodeURIComponent(toolId)}`,
    parseToolVersions,
  );
  const [chosen, setChosen] = useState<number | null>(null);
  if (state.kind !== "ready") {
    return (
      <LoadState
        state={state}
        what="this tool"
        notFound="That tool isn't in the catalog."
        onRetry={reload}
        pending={pending}
      />
    );
  }
  const versions: ToolVersions = state.value;
  const newest = versions.versions.at(-1);
  if (newest === undefined) return null;
  const tool =
    versions.versions.find((item) => item.version === chosen) ?? newest;
  const fix = repair(tool);
  const Icon = GROUP_ICONS[tool.group] ?? Wrench;
  const approval = tool.approval !== "never";
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
        <dl
          data-field="guide"
          className="grid gap-3 border-t pt-4 sm:grid-cols-3"
        >
          {(
            [
              ["What", tool.guide.what],
              ["When", tool.guide.when],
              ["Why", tool.guide.why],
            ] as const
          ).map(([term, text]) => (
            <div key={term} className="space-y-1">
              <dt className="text-muted-foreground text-xs font-semibold tracking-wide">
                {term}
              </dt>
              <dd
                data-guide={term.toLowerCase()}
                className="text-[13.5px] leading-relaxed"
              >
                {text}
              </dd>
            </div>
          ))}
        </dl>
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
            {approval ? APPROVAL_TEXT[tool.approval] : "Not needed"}
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
            {keySource(tool) ?? "None"}
          </dd>
        </dl>
        <dl className="space-y-2 border-t pt-4">
          <dt className="text-muted-foreground text-xs font-semibold tracking-wide">
            Can be granted by
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
      <Grants toolId={tool.tool_id} />
      <CopySchema schema={tool.input_schema} version={tool.version} />
      <FieldTable tool={tool} direction="input" />
      <FieldTable tool={tool} direction="output" />
      <details className="text-sm">
        <summary className="cursor-pointer font-semibold">JSON Schema</summary>
        <pre
          tabIndex={0}
          className="border-border bg-background mt-2 overflow-x-auto rounded-lg border px-3.5 py-3 font-mono text-xs leading-relaxed"
        >
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

// PRD-Studio TL-02: Experts whose latest version grants this tool, and published workflows that reach it.
function Grants({ toolId }: { toolId: string }) {
  const { state, pending, reload } = useResource(
    `/api/v1/tools/${encodeURIComponent(toolId)}/grants`,
    parseToolGrants,
  );
  return (
    <section
      aria-labelledby={`grants-${toolId}`}
      data-field="granted-to"
      className="space-y-2"
    >
      <h3 id={`grants-${toolId}`} className="text-sm font-semibold">
        Granted to
      </h3>
      {state.kind !== "ready" ? (
        <LoadState
          state={state}
          what="the Experts and workflows that grant it"
          onRetry={reload}
          pending={pending}
        />
      ) : state.value.experts.length === 0 &&
        state.value.workflows.length === 0 ? (
        <LoadEmpty>No Expert or published workflow grants it.</LoadEmpty>
      ) : (
        <ul className="flex flex-wrap gap-2 text-[12.5px]">
          {state.value.experts.map((item) => (
            <li key={item.id} data-granted-expert={item.id}>
              <Link
                href={`/experts/${item.id}`}
                className="border-border inline-block rounded-full border px-2.5 py-0.5 underline-offset-4 hover:underline"
              >
                Expert {item.name}, version {item.version}
              </Link>
            </li>
          ))}
          {state.value.workflows.map((item) => (
            <li key={item.id} data-granted-workflow={item.id}>
              <Link
                href={`/workflows/${item.id}`}
                className="border-border inline-block rounded-full border px-2.5 py-0.5 underline-offset-4 hover:underline"
              >
                Workflow {item.name}, version {item.version}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

// PRD-Studio TL-03: exactly the shown version's input schema.
function CopySchema({ schema, version }: { schema: unknown; version: number }) {
  const [copied, setCopied] = useState<string | null>(null);
  async function copy(): Promise<void> {
    try {
      await navigator.clipboard.writeText(JSON.stringify(schema, null, 2));
      setCopied(`Copied the input schema of version ${version}.`);
    } catch {
      setCopied("Copying isn't allowed here.");
    }
  }
  return (
    <div className="flex items-center gap-3">
      <Button variant="outline" size="sm" onClick={() => void copy()}>
        Copy schema
      </Button>
      {copied === null ? null : (
        <p role="status" data-message="copied" className="text-[13px]">
          {copied}
        </p>
      )}
    </div>
  );
}
