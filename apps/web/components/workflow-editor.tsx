"use client";

import {
  parseBlockCatalog,
  parseExecutionBinding,
  parseWorkflowValidation,
  parseWorkflowView,
  type BlockCatalog,
  type WorkflowValidation,
  type WorkflowView,
} from "@autobots/api-client";
import {
  CircleAlert,
  CircleCheck,
  ListChecks,
  Play,
  Upload,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { RunDisclosure } from "@/components/run-disclosure";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Select, Textarea } from "@/components/ui/field";
import { SectionLabel } from "@/components/ui/page-header";
import { csrfFetch } from "@/lib/csrf-fetch";
import { cn } from "@/lib/utils";

const STARTER = JSON.stringify(
  {
    nodes: [
      { id: "in", block: "input", version: 1, config: { type: "string" } },
      { id: "out", block: "output", version: 1 },
    ],
    links: [
      {
        source: "in",
        source_port: "value",
        target: "out",
        target_port: "value",
      },
    ],
  },
  null,
  2,
);

function parsed(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

type DraftNode = { id: string; block: string; label?: string | null };
type DraftGraph = {
  nodes: DraftNode[];
  ir_version?: number | null;
  [key: string]: unknown;
};

function draftGraph(text: string): DraftGraph | null {
  const graph = parsed(text) as DraftGraph | null;
  return graph !== null &&
    typeof graph === "object" &&
    Array.isArray(graph.nodes) &&
    graph.nodes.every(
      (node) => typeof node === "object" && typeof node?.id === "string",
    )
    ? graph
    : null;
}

// What the API returns carries `label: null` and `ir_version: null` where nothing is set. Left out
// here, so an unlabelled graph stays at IR version 1 and keeps its hash.
function tidy(graph: unknown): string {
  const plain = JSON.parse(JSON.stringify(graph)) as DraftGraph;
  if (plain.ir_version === null) delete plain.ir_version;
  for (const node of plain.nodes ?? []) {
    if (node.label === null) delete node.label;
  }
  return JSON.stringify(plain, null, 2);
}

// PRD-Studio WF-06: a label bumps the graph to IR version 2, and with none left it returns to 1.
function withLabel(text: string, nodeId: string, label: string): string {
  const graph = draftGraph(text);
  if (graph === null) return text;
  for (const node of graph.nodes) {
    if (node.id !== nodeId) continue;
    if (label.trim() === "") delete node.label;
    else node.label = label;
  }
  if (graph.nodes.some((node) => typeof node.label === "string")) {
    graph.ir_version = 2;
  } else {
    delete graph.ir_version;
  }
  return JSON.stringify(graph, null, 2);
}

export function WorkflowEditor({ workflowId }: { workflowId: string }) {
  const router = useRouter();
  const [workflow, setWorkflow] = useState<WorkflowView | null>(null);
  const [catalog, setCatalog] = useState<BlockCatalog | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const [draft, setDraft] = useState(STARTER);
  const [check, setCheck] = useState<WorkflowValidation | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [chosen, setChosen] = useState<number | null>(null);
  const [inputs, setInputs] = useState("{}");
  const [description, setDescription] = useState("");

  useEffect(() => {
    let active = true;
    const base = `/api/v1/workflows/${encodeURIComponent(workflowId)}`;
    fetch(base, { cache: "no-store" })
      .then(async (reply) => {
        if (!active) return;
        if (!reply.ok) {
          setUnavailable(true);
          return;
        }
        const loaded = parseWorkflowView(await reply.json());
        setWorkflow(loaded);
        setDescription(loaded.description ?? "");
        const latest = loaded.versions.at(-1);
        if (latest !== undefined) {
          setDraft(tidy(latest.graph));
          setChosen(latest.version);
        }
      })
      .catch(() => {
        if (active) setUnavailable(true);
      });
    fetch("/api/v1/workflow-blocks", { cache: "no-store" })
      .then(async (reply) => {
        if (active && reply.ok)
          setCatalog(parseBlockCatalog(await reply.json()));
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [workflowId]);

  async function validate(): Promise<void> {
    setMessage(null);
    const graph = parsed(draft);
    if (graph === null) {
      setCheck(null);
      setMessage("That isn't valid JSON.");
      return;
    }
    const reply = await csrfFetch("/api/v1/workflows/validate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(graph),
    }).catch(() => null);
    if (reply?.ok === true) {
      setCheck(parseWorkflowValidation(await reply.json()));
    } else {
      setCheck(null);
      setMessage("That has the wrong shape for a workflow.");
    }
  }

  async function publish(): Promise<void> {
    if (workflow === null) return;
    setMessage(null);
    const reply = await csrfFetch(
      `/api/v1/workflows/${encodeURIComponent(workflow.id)}/versions`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: JSON.stringify({
          expected_version: workflow.latest_version,
          graph: parsed(draft),
        }),
      },
    ).catch(() => null);
    if (reply?.ok === true) {
      const saved = parseWorkflowView(await reply.json());
      setWorkflow(saved);
      setChosen(saved.latest_version);
      setMessage(
        `Published as version ${saved.latest_version}. Earlier versions don't change.`,
      );
      return;
    }
    const failure = (await reply?.json().catch(() => null)) as {
      code?: string;
      message?: string;
    } | null;
    setMessage(
      failure?.code === "owner_required"
        ? "Only the workspace owner can publish."
        : (failure?.message ?? "That could not be published."),
    );
  }

  async function saveDescription(): Promise<void> {
    if (workflow === null) return;
    setMessage(null);
    const text = description.trim();
    const reply = await csrfFetch(
      `/api/v1/workflows/${encodeURIComponent(workflow.id)}/description`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ description: text === "" ? null : text }),
      },
    ).catch(() => null);
    if (reply?.ok === true) {
      const saved = parseWorkflowView(await reply.json());
      setWorkflow(saved);
      setDescription(saved.description ?? "");
      setMessage(
        saved.description === null
          ? "The description is removed. No version changed."
          : "Description saved. No version changed.",
      );
      return;
    }
    const failure = (await reply?.json().catch(() => null)) as {
      code?: string;
    } | null;
    setMessage(
      failure?.code === "owner_required"
        ? "Only the workspace owner can describe a workflow."
        : "The description could not be saved.",
    );
  }

  async function run(): Promise<void> {
    if (workflow === null || chosen === null) return;
    setMessage(null);
    const values = parsed(inputs);
    if (values === null) {
      setMessage("The inputs aren't valid JSON.");
      return;
    }
    const reply = await csrfFetch(
      `/api/v1/workflows/${encodeURIComponent(workflow.id)}/executions`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: JSON.stringify({ version: chosen, inputs: values }),
      },
    ).catch(() => null);
    if (reply?.ok === true) {
      router.push(
        `/workflow-executions/${parseExecutionBinding(await reply.json()).id}`,
      );
      return;
    }
    const failure = (await reply?.json().catch(() => null)) as {
      message?: string;
    } | null;
    setMessage(failure?.message ?? "That could not be started.");
  }

  if (unavailable) {
    return (
      <p role="alert" data-state="unavailable" className="text-sm">
        That workflow is not available.
      </p>
    );
  }
  if (workflow === null) {
    return (
      <p role="status" className="text-muted-foreground text-sm">
        Loading this workflow.
      </p>
    );
  }
  return (
    <div
      className={cn(
        "grid items-start gap-6",
        catalog === null ? "" : "@4xl:grid-cols-[minmax(0,1fr)_320px]",
      )}
    >
      <Card
        aria-labelledby="graph-heading"
        className="space-y-4 p-6 @4xl:col-start-1 @4xl:row-start-1"
      >
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <h2
            id="graph-heading"
            className="font-serif text-[22px] leading-tight font-normal tracking-tight wrap-anywhere"
          >
            {workflow.name}
          </h2>
          {workflow.latest_version === 0 ? (
            <Badge variant="attention" dot>
              Not published
            </Badge>
          ) : (
            <Badge variant="outline">Version {workflow.latest_version}</Badge>
          )}
        </div>
        <div className="space-y-1.5">
          <label htmlFor="workflow-description" className={SECTION}>
            Description
          </label>
          <Textarea
            id="workflow-description"
            rows={2}
            maxLength={500}
            value={description}
            placeholder="What this workflow does"
            onChange={(event) => setDescription(event.target.value)}
          />
          <Button
            variant="outline"
            size="sm"
            onClick={() => void saveDescription()}
          >
            Save description
          </Button>
        </div>
        <div className="space-y-1.5">
          <label htmlFor="graph" className={SECTION}>
            Graph
          </label>
          <Textarea
            id="graph"
            rows={16}
            spellCheck={false}
            value={draft}
            onChange={(event) => {
              setDraft(event.target.value);
              setCheck(null);
            }}
            className="font-mono text-[12.5px] leading-relaxed"
          />
        </div>
        {draftGraph(draft) === null ? null : (
          <fieldset data-field="step-labels" className="min-w-0 space-y-2">
            <legend className={cn(SECTION, "mb-1")}>Step labels</legend>
            <p className="text-muted-foreground text-[12.5px]">
              Optional. A label says what a step does, and a labelled graph is
              published at IR version 2.
            </p>
            {draftGraph(draft)!.nodes.map((node) => (
              <div
                key={node.id}
                className="flex flex-wrap items-center gap-x-3 gap-y-1"
              >
                <label
                  htmlFor={`label-${node.id}`}
                  className="w-40 shrink-0 font-mono text-[12.5px] break-all"
                >
                  {node.id} ({node.block})
                </label>
                <Input
                  id={`label-${node.id}`}
                  maxLength={80}
                  value={typeof node.label === "string" ? node.label : ""}
                  onChange={(event) => {
                    setDraft(withLabel(draft, node.id, event.target.value));
                    setCheck(null);
                  }}
                  className="h-8 min-w-0 flex-1"
                />
              </div>
            ))}
          </fieldset>
        )}
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => void validate()}>
            <ListChecks aria-hidden="true" />
            Validate
          </Button>
          <Button onClick={() => void publish()}>
            <Upload aria-hidden="true" />
            Publish
          </Button>
        </div>
        {check === null ? null : check.valid ? (
          <p
            role="status"
            data-validation="valid"
            className="flex items-center gap-2 text-sm"
          >
            <CircleCheck
              aria-hidden="true"
              className="text-success-text size-4 shrink-0"
            />
            <span>
              <span className="text-success-text font-medium">Valid.</span> Hash{" "}
              <span className="font-mono text-[12.5px]">
                {check.graph_hash?.slice(0, 12)}
              </span>
              .
            </span>
          </p>
        ) : (
          <div
            role="alert"
            data-validation="invalid"
            className="border-destructive/35 space-y-1.5 rounded-lg border p-3 text-sm"
          >
            <p className="text-destructive flex items-center gap-2 font-medium">
              <CircleAlert aria-hidden="true" className="size-4 shrink-0" />
              This can&apos;t be published yet:
            </p>
            <ul className="list-disc space-y-0.5 pl-10">
              {check.errors.map((error, index) => (
                <li key={`${error.code}-${index}`} data-error={error.code}>
                  {error.code.replaceAll("_", " ")}
                  {error.node === null ? "" : ` at ${error.node}`}
                  {error.port === null ? "" : `, port ${error.port}`}
                </li>
              ))}
            </ul>
          </div>
        )}
        {message === null ? null : (
          <p role="status" data-message="editor" className="text-sm">
            {message}
          </p>
        )}
      </Card>
      <Card
        aria-labelledby="run-heading"
        className="space-y-4 p-6 @4xl:col-start-1 @4xl:row-start-2"
      >
        <h2
          id="run-heading"
          className="font-serif text-[22px] leading-tight font-normal tracking-tight"
        >
          Run a version
        </h2>
        {workflow.versions.length === 0 ? (
          <p className="text-muted-foreground text-sm">
            Publish a version first.
          </p>
        ) : (
          <>
            <div className="space-y-1.5">
              <label htmlFor="version" className={SECTION}>
                Version
              </label>
              <Select
                id="version"
                value={chosen ?? ""}
                onChange={(event) => setChosen(Number(event.target.value))}
                className="sm:max-w-md"
              >
                {workflow.versions.map((version) => (
                  <option key={version.version} value={version.version}>
                    Version {version.version}, {version.graph_hash.slice(0, 12)}
                    {version.source === "model_proposal"
                      ? ", from a model"
                      : ""}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-1.5">
              <label htmlFor="inputs" className={SECTION}>
                Inputs
              </label>
              <Textarea
                id="inputs"
                rows={3}
                spellCheck={false}
                value={inputs}
                onChange={(event) => setInputs(event.target.value)}
                className="font-mono text-[12.5px] leading-relaxed"
              />
            </div>
            <RunDisclosure
              sendsOnlyIfAgent
              usesModel={
                workflow.versions
                  .find((version) => version.version === chosen)
                  ?.graph.nodes?.some((node) => node.block === "agent") ?? false
              }
            />
            <div className="flex justify-end border-t pt-4">
              <Button onClick={() => void run()}>
                <Play aria-hidden="true" />
                Run this version
              </Button>
            </div>
          </>
        )}
      </Card>
      {catalog === null ? null : (
        <Card
          aria-labelledby="blocks-heading"
          className="space-y-3 @4xl:col-start-2 @4xl:row-span-2 @4xl:row-start-1"
        >
          <SectionLabel id="blocks-heading">Blocks</SectionLabel>
          <table className="w-full text-left text-[13px]">
            <thead>
              <tr className="border-b">
                <th
                  scope="col"
                  className="text-muted-foreground pr-2 pb-2 text-xs font-medium"
                >
                  Block
                </th>
                <th
                  scope="col"
                  className="text-muted-foreground px-2 pb-2 text-xs font-medium"
                >
                  Inputs
                </th>
                <th
                  scope="col"
                  className="text-muted-foreground pb-2 pl-2 text-xs font-medium"
                >
                  Outputs
                </th>
              </tr>
            </thead>
            <tbody>
              {catalog.blocks.map((block) => (
                <tr
                  key={block.block}
                  data-block={block.block}
                  className="border-b align-top last:border-b-0"
                >
                  <td className="py-2 pr-2 font-mono text-[12px] font-medium wrap-anywhere">
                    {block.block} v{block.version}
                  </td>
                  <td className="text-muted-foreground px-2 py-2 font-mono text-[12px] wrap-anywhere">
                    {block.inputs.join(", ") || "none"}
                  </td>
                  <td className="text-muted-foreground py-2 pl-2 font-mono text-[12px] wrap-anywhere">
                    {block.outputs.join(", ") || "none"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}

// A form section's label, in the Studio's small label style. It stays the control's native label.
const SECTION = "text-muted-foreground text-xs font-semibold tracking-wide";
