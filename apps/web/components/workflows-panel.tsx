"use client";

import {
  parseWorkflowList,
  parseWorkflowView,
  type WorkflowView,
} from "@autobots/api-client";
import { Plus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { IconTile } from "@/components/ui/card";
import { Input } from "@/components/ui/field";
import { SectionLabel } from "@/components/ui/page-header";
import { csrfFetch } from "@/lib/csrf-fetch";

export function WorkflowsPanel() {
  const router = useRouter();
  const [workflows, setWorkflows] = useState<readonly WorkflowView[] | null>(
    null,
  );
  const [failed, setFailed] = useState(false);
  const [name, setName] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetch("/api/v1/workflows", { cache: "no-store" })
      .then(async (reply) => {
        if (!active) return;
        if (reply.ok)
          setWorkflows(parseWorkflowList(await reply.json()).workflows);
        else setFailed(true);
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
    };
  }, []);

  async function create(event: FormEvent): Promise<void> {
    event.preventDefault();
    setMessage(null);
    const reply = await csrfFetch("/api/v1/workflows", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": crypto.randomUUID(),
      },
      body: JSON.stringify({ name }),
    }).catch(() => null);
    if (reply?.ok === true) {
      router.push(`/workflows/${parseWorkflowView(await reply.json()).id}`);
      return;
    }
    const failure = (await reply?.json().catch(() => null)) as {
      code?: string;
    } | null;
    setMessage(
      failure?.code === "owner_required"
        ? "Only the workspace owner can create a workflow."
        : failure?.code === "workflow_name_taken"
          ? "That name is already used."
          : "That could not be saved.",
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
  return (
    <>
      <section aria-labelledby="list-heading" className="space-y-3">
        <SectionLabel id="list-heading">Your workflows</SectionLabel>
        {workflows.length === 0 ? (
          <p className="text-muted-foreground rounded-xl border border-dashed p-6 text-sm">
            No workflows yet.
          </p>
        ) : (
          <table className="w-full text-left text-[13.5px]">
            <thead>
              <tr className="border-b">
                <th
                  scope="col"
                  className="text-muted-foreground pr-3 pb-2.5 text-[12.5px] font-medium"
                >
                  Workflow
                </th>
                <th
                  scope="col"
                  className="text-muted-foreground px-3 pb-2.5 text-[12.5px] font-medium"
                >
                  Version
                </th>
                <th
                  scope="col"
                  className="text-muted-foreground hidden px-3 pb-2.5 text-right text-[12.5px] font-medium @xl:table-cell"
                >
                  Nodes
                </th>
                <th
                  scope="col"
                  className="text-muted-foreground hidden pb-2.5 pl-3 text-[12.5px] font-medium @xl:table-cell"
                >
                  Graph hash
                </th>
              </tr>
            </thead>
            <tbody>
              {workflows.map((workflow) => {
                const latest = workflow.versions.at(-1);
                return (
                  <tr key={workflow.id} className="border-b">
                    <td className="py-3.5 pr-3 align-middle">
                      <Link
                        href={`/workflows/${workflow.id}`}
                        className="font-medium wrap-anywhere underline-offset-4 hover:underline"
                      >
                        {workflow.name}
                      </Link>
                    </td>
                    <td className="px-3 py-3.5 align-middle">
                      {workflow.latest_version === 0 ? (
                        <Badge variant="attention" dot>
                          Not published
                        </Badge>
                      ) : (
                        <Badge variant="outline">
                          Version {workflow.latest_version}
                        </Badge>
                      )}
                    </td>
                    <td className="hidden px-3 py-3.5 text-right align-middle font-mono text-[12.5px] tabular-nums @xl:table-cell">
                      {latest?.graph.nodes?.length ?? (
                        <span className="text-muted-foreground">none</span>
                      )}
                    </td>
                    <td className="text-muted-foreground hidden py-3.5 pl-3 align-middle font-mono text-[12.5px] @xl:table-cell">
                      {latest === undefined
                        ? "none"
                        : latest.graph_hash.slice(0, 12)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>
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
            />
          </div>
          <Button type="submit" disabled={name.trim() === ""}>
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
