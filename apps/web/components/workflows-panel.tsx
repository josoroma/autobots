"use client";

import {
  parseWorkflowExecutionList,
  parseWorkflowList,
  parseWorkflowPreview,
  parseWorkflowView,
  type WorkflowExecutionList,
  type WorkflowPreview,
  type WorkflowView,
} from "@autobots/api-client";
import { Plus, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { HeldNote } from "@/components/held-note";
import { STATUS_TEXT } from "@/components/run-list";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { IconTile } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/field";
import { SectionLabel } from "@/components/ui/page-header";
import { csrfFetch } from "@/lib/csrf-fetch";
import { cn } from "@/lib/utils";
import { withHeld } from "@/lib/submit";
import { useSubmit } from "@/lib/use-submit";

type Tab = "all" | "published" | "drafts";
const TABS: { id: Tab; label: string }[] = [
  { id: "all", label: "All" },
  { id: "published", label: "Published" },
  { id: "drafts", label: "Drafts" },
];
type Execution = WorkflowExecutionList["executions"][number];

const RELATIVE = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

function relative(iso: string, now: number): string {
  const elapsed = Date.parse(iso) - now;
  for (const [unit, size] of [
    ["day", 86_400_000],
    ["hour", 3_600_000],
    ["minute", 60_000],
  ] as const) {
    if (Math.abs(elapsed) >= size) {
      return RELATIVE.format(Math.round(elapsed / size), unit);
    }
  }
  return "just now";
}

function dollars(micro: number): string {
  return `US$${(micro / 1_000_000).toFixed(2)}`;
}

// WF-04: an estimate while a reservation is held or a charge was never reported.
function spend(execution: Execution): string {
  const estimated = execution.reserved_micro_usd > 0 || execution.unreported;
  const amount = dollars(
    execution.charged_micro_usd + execution.reserved_micro_usd,
  );
  return estimated ? `≈ ${amount}, estimated` : `${amount}, reported`;
}

function duration(seconds: number | null): string {
  if (seconds === null) return "still running";
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return minutes === 0
    ? `${rest}s`
    : `${minutes}m ${String(rest).padStart(2, "0")}s`;
}

function stateText(status: string): string {
  return STATUS_TEXT[status] ?? status;
}

const TH = "text-muted-foreground px-3 pb-2.5 text-[12.5px] font-medium";
const TD = "px-3 py-3.5 align-top";
// At 400% zoom the list keeps the name, version and Preview, so nothing scrolls sideways.
const NARROW_HIDDEN = "hidden @xl:table-cell";

// PRD-Studio WF-01, WF-03 and WF-04: tabs, search, the rows' facts, and the selected workflow's
// preview and recent executions. The preview sits under the list, so Tab never climbs.
const CREATE_REFUSALS: Readonly<Record<string, string>> = {
  owner_required: "Only the workspace owner can create a workflow.",
  workflow_name_taken: "That name is already used.",
};

export function WorkflowsPanel() {
  // One write at a time, and one key per intent until its outcome is known (Decision 0027 D2).
  const creates = useSubmit();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const tab = (params.get("tab") as Tab | null) ?? "all";
  const query = (params.get("q") ?? "").trim().toLowerCase();
  const selected = params.get("workflow");
  const [workflows, setWorkflows] = useState<readonly WorkflowView[] | null>(
    null,
  );
  const [failed, setFailed] = useState(false);
  const [name, setName] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [now, setNow] = useState(0);

  useEffect(() => {
    let active = true;
    fetch("/api/v1/workflows", { cache: "no-store" })
      .then(async (reply) => {
        if (!active) return;
        if (reply.ok) {
          setWorkflows(parseWorkflowList(await reply.json()).workflows);
          setNow(Date.now());
        } else setFailed(true);
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
    };
  }, []);

  function href(changes: Record<string, string | null>): string {
    const next = new URLSearchParams(params.toString());
    for (const [key, value] of Object.entries(changes)) {
      if (value === null || value === "") next.delete(key);
      else next.set(key, value);
    }
    const rest = next.toString();
    return rest === "" ? pathname : `${pathname}?${rest}`;
  }

  async function create(event: FormEvent): Promise<void> {
    event.preventDefault();
    setMessage(null);
    const result = await creates.submit({
      body: () => JSON.stringify({ name }),
      send: ({ key, body }) =>
        csrfFetch("/api/v1/workflows", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": key,
          },
          body,
        }),
      parse: parseWorkflowView,
    });
    if (result === null) return;
    if (result.outcome === "accepted" && result.value !== null) {
      router.push(`/workflows/${result.value.id}`);
      return;
    }
    setMessage(
      result.outcome === "unknown"
        ? "The reply was lost, so it may have been created. Pressing again won't create a second one."
        : withHeld(
            CREATE_REFUSALS[result.refusal?.code ?? ""] ??
              "That could not be saved.",
            result.held,
          ),
    );
  }

  if (failed) {
    return (
      <p role="alert" className="text-sm">
        Workflows could not be loaded. Sign in, then try again.
      </p>
    );
  }
  if (workflows === null) {
    return (
      <p role="status" className="text-muted-foreground text-sm">
        Loading workflows.
      </p>
    );
  }
  const inTab = (workflow: WorkflowView, which: Tab): boolean =>
    which === "all" ||
    (which === "published"
      ? workflow.latest_version > 0
      : workflow.draft !== null);
  const shown = workflows.filter(
    (workflow) =>
      inTab(workflow, tab) &&
      (query === "" || workflow.name.toLowerCase().includes(query)),
  );
  const chosen = workflows.find((workflow) => workflow.id === selected) ?? null;
  return (
    <>
      <section aria-labelledby="list-heading" className="space-y-3">
        <SectionLabel id="list-heading">Your workflows</SectionLabel>
        <div className="flex flex-wrap items-end gap-x-4 gap-y-2">
          <nav aria-label="Workflow tabs" className="flex gap-1">
            {TABS.map((item) => (
              <Link
                key={item.id}
                href={href({ tab: item.id === "all" ? null : item.id })}
                scroll={false}
                aria-current={tab === item.id ? "page" : undefined}
                data-tab={item.id}
                className={cn(
                  "rounded-lg border px-3 py-1.5 text-[13px]",
                  tab === item.id
                    ? "border-foreground font-medium"
                    : "border-transparent",
                )}
              >
                {item.label}{" "}
                <span className="text-muted-foreground tabular-nums">
                  {
                    workflows.filter((workflow) => inTab(workflow, item.id))
                      .length
                  }
                </span>
              </Link>
            ))}
          </nav>
          <label className="ml-auto flex items-center gap-2 text-[13px]">
            <span className="text-muted-foreground">Search</span>
            <Input
              type="search"
              defaultValue={params.get("q") ?? ""}
              placeholder="Workflow name"
              onChange={(event) =>
                router.replace(href({ q: event.target.value.trim() }), {
                  scroll: false,
                })
              }
              className="h-8 w-48"
            />
          </label>
        </div>
        {shown.length === 0 ? (
          <p className="text-muted-foreground rounded-xl border border-dashed p-6 text-sm">
            {workflows.length === 0
              ? "No workflows yet."
              : "No workflow matches."}
          </p>
        ) : (
          <div
            tabIndex={0}
            role="region"
            aria-label="Workflows table"
            className="overflow-x-auto"
          >
            <table className="w-full text-left text-[13.5px]">
              <thead>
                <tr className="border-b">
                  <th scope="col" className={cn(TH, "pl-0")}>
                    Workflow
                  </th>
                  <th scope="col" className={cn(TH, NARROW_HIDDEN)}>
                    Experts
                  </th>
                  <th scope="col" className={TH}>
                    Version
                  </th>
                  <th
                    scope="col"
                    className={cn(TH, NARROW_HIDDEN, "text-right")}
                  >
                    Steps
                  </th>
                  <th scope="col" className={cn(TH, NARROW_HIDDEN)}>
                    Last execution
                  </th>
                  <th
                    scope="col"
                    className={cn(TH, NARROW_HIDDEN, "text-right")}
                  >
                    Runs
                  </th>
                  <th scope="col" className={cn(TH, "pr-0")}>
                    <span className="sr-only">Preview</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {shown.map((workflow) => (
                  <tr
                    key={workflow.id}
                    data-workflow={workflow.id}
                    className="border-b"
                  >
                    <td className={cn(TD, "pl-0")}>
                      <Link
                        href={`/workflows/${workflow.id}`}
                        className="font-medium wrap-anywhere underline-offset-4 hover:underline"
                      >
                        {workflow.name}
                      </Link>
                      {workflow.description === null ? null : (
                        <p
                          data-field="description"
                          className="text-muted-foreground mt-0.5 text-[12.5px] wrap-anywhere"
                        >
                          {workflow.description}
                        </p>
                      )}
                    </td>
                    <td
                      data-field="experts"
                      className={cn(TD, NARROW_HIDDEN, "text-[12.5px]")}
                    >
                      {workflow.experts.length === 0 ? (
                        <span className="text-muted-foreground">None</span>
                      ) : (
                        workflow.experts.join(" → ")
                      )}
                    </td>
                    <td className={TD}>
                      <span className="flex flex-wrap gap-1.5">
                        {workflow.latest_version === 0 ? (
                          <Badge variant="attention" dot>
                            Not published
                          </Badge>
                        ) : (
                          <Badge variant="outline">
                            Version {workflow.latest_version}
                          </Badge>
                        )}
                        {workflow.draft === null ? null : (
                          <Badge variant="attention" data-field="has-draft">
                            Draft
                          </Badge>
                        )}
                      </span>
                    </td>
                    <td
                      data-field="steps"
                      className={cn(
                        TD,
                        NARROW_HIDDEN,
                        "text-right tabular-nums",
                      )}
                    >
                      {workflow.step_count}
                    </td>
                    <td
                      data-field="last-execution"
                      className={cn(TD, NARROW_HIDDEN, "text-[12.5px]")}
                    >
                      {workflow.last_execution === null ? (
                        <span className="text-muted-foreground">Never run</span>
                      ) : (
                        <>
                          {stateText(workflow.last_execution.status)}
                          <span className="text-muted-foreground">
                            {", "}
                            <time dateTime={workflow.last_execution.started_at}>
                              {relative(
                                workflow.last_execution.started_at,
                                now,
                              )}
                            </time>
                          </span>
                        </>
                      )}
                    </td>
                    <td
                      data-field="runs"
                      className={cn(
                        TD,
                        NARROW_HIDDEN,
                        "text-right tabular-nums",
                      )}
                    >
                      {workflow.run_count}
                    </td>
                    <td className={cn(TD, "pr-0 text-right")}>
                      <Link
                        href={href({ workflow: workflow.id, version: null })}
                        scroll={false}
                        aria-current={
                          workflow.id === selected ? "true" : undefined
                        }
                        aria-label={`Preview ${workflow.name}`}
                        className="text-[13px] underline underline-offset-4"
                      >
                        Preview
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      {chosen === null ? null : (
        <WorkflowPreviewPanel
          key={chosen.id}
          workflow={chosen}
          version={params.get("version")}
          versionHref={(value) => href({ version: value })}
          now={now}
        />
      )}
      <section
        aria-labelledby="create-heading"
        className="space-y-3 rounded-xl border border-dashed p-5"
      >
        <div className="flex items-center gap-3">
          <IconTile icon={Plus} className="rounded-full" />
          <h2 id="create-heading" className="text-[15px] font-semibold">
            New workflow
          </h2>
        </div>
        <form
          onSubmit={(event) => void create(event)}
          className="flex flex-col gap-3 sm:flex-row sm:items-end"
        >
          <div className="min-w-0 flex-1 space-y-1.5 sm:max-w-sm">
            <label htmlFor="workflow-name" className="text-sm font-medium">
              Name
            </label>
            <Input
              id="workflow-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              maxLength={100}
              readOnly={creates.holding()}
            />
            {creates.holding() ? <HeldNote /> : null}
          </div>
          <Button
            type="submit"
            disabled={name.trim() === "" || creates.pending}
          >
            <Plus aria-hidden="true" />
            Create
          </Button>
        </form>
        {message === null ? null : (
          <p role="alert" className="text-sm">
            {message}
          </p>
        )}
      </section>
    </>
  );
}

function WorkflowPreviewPanel({
  workflow,
  version,
  versionHref,
  now,
}: {
  workflow: WorkflowView;
  version: string | null;
  versionHref: (value: string) => string;
  now: number;
}) {
  const router = useRouter();
  // The latest published version first, else the draft.
  const shown =
    version ??
    (workflow.latest_version > 0
      ? String(workflow.latest_version)
      : workflow.draft !== null
        ? "draft"
        : null);
  const [preview, setPreview] = useState<WorkflowPreview | null>(null);
  const [executions, setExecutions] = useState<WorkflowExecutionList | null>(
    null,
  );
  const heading = useRef<HTMLHeadingElement>(null);

  // The preview sits under the list, often below the fold, and the Preview link doesn't scroll.
  // So choosing a workflow brings its preview into view and moves focus to its heading, which
  // also tells a screen reader where it went. Changing the version keeps the place.
  useEffect(() => {
    const target = heading.current;
    if (target === null) return;
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    target.focus({ preventScroll: true });
    target.scrollIntoView({
      block: "start",
      behavior: still ? "auto" : "smooth",
    });
  }, [workflow.id]);

  useEffect(() => {
    let active = true;
    if (shown !== null) {
      fetch(
        `/api/v1/workflows/${encodeURIComponent(workflow.id)}/preview?version=${encodeURIComponent(shown)}`,
        { cache: "no-store" },
      )
        .then(async (reply) => {
          if (!active) return;
          if (reply.ok) setPreview(parseWorkflowPreview(await reply.json()));
          else await reply.text();
        })
        .catch(() => undefined);
    }
    return () => {
      active = false;
    };
  }, [workflow.id, shown]);

  useEffect(() => {
    let active = true;
    fetch(`/api/v1/workflows/${encodeURIComponent(workflow.id)}/executions`, {
      cache: "no-store",
    })
      .then(async (reply) => {
        if (!active) return;
        if (reply.ok)
          setExecutions(parseWorkflowExecutionList(await reply.json()));
        else await reply.text();
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [workflow.id]);

  const steps =
    preview !== null && String(preview.version) === shown
      ? preview.steps
      : null;
  return (
    <section
      aria-labelledby="preview-heading"
      data-panel={workflow.id}
      className="space-y-5 rounded-xl border p-5"
    >
      <div className="flex flex-wrap items-end gap-x-4 gap-y-2">
        <h2
          id="preview-heading"
          ref={heading}
          tabIndex={-1}
          className="scroll-mt-4 text-[15px] font-semibold outline-none"
        >
          Preview: {workflow.name}
        </h2>
        {shown === null ? null : (
          <label className="ml-auto flex items-center gap-2 text-[13px]">
            <span className="text-muted-foreground">Version</span>
            <Select
              value={shown}
              onChange={(event) =>
                router.replace(versionHref(event.target.value), {
                  scroll: false,
                })
              }
              className="h-8 w-40"
            >
              {[...workflow.versions].reverse().map((item) => (
                <option key={item.version} value={String(item.version)}>
                  Version {item.version}
                </option>
              ))}
              {workflow.draft === null ? null : (
                <option value="draft">Draft</option>
              )}
            </Select>
          </label>
        )}
      </div>
      {shown === null ? (
        <p className="text-muted-foreground text-sm">
          Nothing is published or drafted yet.
        </p>
      ) : steps === null ? (
        <p className="text-muted-foreground text-sm">Loading its steps.</p>
      ) : (
        <ol data-field="preview-steps" className="space-y-2 text-[13.5px]">
          {steps.map((step, index) => (
            <li
              key={step.id}
              data-step={step.id}
              className="border-border rounded-lg border px-3.5 py-2.5"
            >
              <p>
                <span className="text-muted-foreground tabular-nums">
                  {index + 1}.
                </span>{" "}
                <span className="font-medium">{step.label ?? step.id}</span>{" "}
                <span className="text-muted-foreground font-mono text-[12px]">
                  {step.block}
                </span>
              </p>
              {step.approval ? (
                <p
                  data-field="approval-gate"
                  className="mt-1 flex items-center gap-1.5 text-[13px] font-medium"
                >
                  <ShieldCheck aria-hidden="true" className="size-3.5" />
                  Approval gate: a person approves before the run continues.
                </p>
              ) : null}
              {step.block === "agent" ? (
                <dl className="text-muted-foreground mt-1 grid gap-x-3 gap-y-0.5 text-[12.5px] sm:grid-cols-[auto_1fr]">
                  <dt>Expert</dt>
                  <dd data-field="step-expert" className="text-foreground">
                    {step.expert_name ?? "Unavailable"}
                  </dd>
                  <dt>Model</dt>
                  <dd
                    data-field="step-model"
                    className="text-foreground font-mono"
                  >
                    {step.model ?? "Unknown"}
                  </dd>
                  <dt>Tools</dt>
                  <dd
                    data-field="step-tools"
                    className="text-foreground font-mono"
                  >
                    {step.tools.length === 0 ? "None" : step.tools.join(", ")}
                  </dd>
                </dl>
              ) : null}
            </li>
          ))}
        </ol>
      )}
      <div className="space-y-2">
        <h3 className="text-sm font-semibold">Recent executions</h3>
        {executions === null ? (
          <p className="text-muted-foreground text-sm">Loading.</p>
        ) : executions.executions.length === 0 ? (
          <p className="text-muted-foreground text-sm">No executions yet.</p>
        ) : (
          <ul className="text-[13px]">
            {executions.executions.map((execution) => (
              <li
                key={execution.id}
                data-execution={execution.id}
                className="flex flex-wrap gap-x-3 gap-y-0.5 border-t py-2"
              >
                <Link
                  href={`/runs/${execution.run_id}`}
                  className="font-medium underline-offset-4 hover:underline"
                >
                  Version {execution.version}
                </Link>
                <span data-field="state">{stateText(execution.status)}</span>
                <span data-field="spend" className="tabular-nums">
                  {spend(execution)}
                </span>
                <span
                  data-field="duration"
                  className="text-muted-foreground tabular-nums"
                >
                  {duration(execution.duration_seconds)}
                </span>
                <time
                  dateTime={execution.started_at}
                  className="text-muted-foreground"
                >
                  {relative(execution.started_at, now)}
                </time>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
