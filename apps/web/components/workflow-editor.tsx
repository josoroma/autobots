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
import { Select, Textarea } from "@/components/ui/field";
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
        const latest = loaded.versions.at(-1);
        if (latest !== undefined) {
          setDraft(JSON.stringify(latest.graph, null, 2));
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
