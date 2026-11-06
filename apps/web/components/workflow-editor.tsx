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
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { RunDisclosure } from "@/components/run-disclosure";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { csrfFetch } from "@/lib/csrf-fetch";

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
const INPUT_CLASS =
  "bg-background border-input block w-full rounded-md border px-3 py-2 font-mono text-sm";

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
      <p role="status" className="text-sm">
        Loading this workflow.
      </p>
    );
  }
  return (
    <>
      <Card aria-labelledby="graph-heading" className="space-y-3">
        <h2 id="graph-heading" className="text-lg font-medium">
          {workflow.name}
        </h2>
        <label htmlFor="graph" className="text-sm font-medium">
          Graph
        </label>
        <textarea
          id="graph"
          rows={16}
          spellCheck={false}
          value={draft}
          onChange={(event) => {
            setDraft(event.target.value);
            setCheck(null);
          }}
          className={INPUT_CLASS}
        />
        <div className="flex gap-3">
          <Button variant="secondary" onClick={() => void validate()}>
            Validate
          </Button>
          <Button onClick={() => void publish()}>Publish</Button>
        </div>
        {check === null ? null : check.valid ? (
          <p role="status" data-validation="valid" className="text-sm">
            Valid. Hash {check.graph_hash?.slice(0, 12)}.
          </p>
        ) : (
          <div
            role="alert"
            data-validation="invalid"
            className="space-y-1 text-sm"
          >
            <p>This can&apos;t be published yet:</p>
            <ul className="list-disc pl-5">
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
      <Card aria-labelledby="run-heading" className="space-y-3">
        <h2 id="run-heading" className="text-lg font-medium">
          Run a version
        </h2>
        {workflow.versions.length === 0 ? (
          <p className="text-sm">Publish a version first.</p>
        ) : (
          <>
            <label htmlFor="version" className="text-sm font-medium">
              Version
            </label>
            <select
              id="version"
              value={chosen ?? ""}
              onChange={(event) => setChosen(Number(event.target.value))}
              className="bg-background border-input block rounded-md border px-3 py-2 text-sm"
            >
              {workflow.versions.map((version) => (
                <option key={version.version} value={version.version}>
                  Version {version.version}, {version.graph_hash.slice(0, 12)}
                  {version.source === "model_proposal" ? ", from a model" : ""}
                </option>
              ))}
            </select>
            <label htmlFor="inputs" className="text-sm font-medium">
              Inputs
            </label>
            <textarea
              id="inputs"
              rows={3}
              spellCheck={false}
              value={inputs}
              onChange={(event) => setInputs(event.target.value)}
              className={INPUT_CLASS}
            />
            <RunDisclosure sendsOnlyIfAgent />
            <Button onClick={() => void run()}>Run this version</Button>
          </>
        )}
      </Card>
      {catalog === null ? null : (
        <Card aria-labelledby="blocks-heading" className="space-y-2">
          <h2 id="blocks-heading" className="text-lg font-medium">
            Blocks
          </h2>
          <table className="w-full text-left text-sm">
            <thead>
              <tr>
                <th scope="col">Block</th>
                <th scope="col">Inputs</th>
                <th scope="col">Outputs</th>
              </tr>
            </thead>
            <tbody>
              {catalog.blocks.map((block) => (
                <tr key={block.block} data-block={block.block}>
                  <td className="py-1 font-medium">
                    {block.block} v{block.version}
                  </td>
                  <td>{block.inputs.join(", ") || "none"}</td>
                  <td>{block.outputs.join(", ") || "none"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </>
  );
}
