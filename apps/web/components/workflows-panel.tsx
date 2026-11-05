"use client";

import {
  parseWorkflowList,
  parseWorkflowView,
  type WorkflowView,
} from "@autobots/api-client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
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
      <p role="status" className="text-sm">
        Loading workflows.
      </p>
    );
  }
  return (
    <>
      <Card aria-labelledby="list-heading" className="space-y-3">
        <h2 id="list-heading" className="text-lg font-medium">
          Your workflows
        </h2>
        {workflows.length === 0 ? (
          <p className="text-sm">No workflows yet.</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {workflows.map((workflow) => (
              <li key={workflow.id}>
                <Link
                  href={`/workflows/${workflow.id}`}
                  className="font-medium underline"
                >
                  {workflow.name}
                </Link>{" "}
                <span className="text-muted-foreground">
                  {workflow.latest_version === 0
                    ? "Not published"
                    : `Version ${workflow.latest_version}`}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Card aria-labelledby="create-heading" className="space-y-3">
        <h2 id="create-heading" className="text-lg font-medium">
          New workflow
        </h2>
        <form onSubmit={(event) => void create(event)} className="space-y-3">
          <label htmlFor="workflow-name" className="text-sm font-medium">
            Name
          </label>
          <input
            id="workflow-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            maxLength={100}
            className="bg-background border-input block w-full rounded-md border px-3 py-2 text-sm"
          />
          <Button type="submit" disabled={name.trim() === ""}>
            Create
          </Button>
        </form>
        {message === null ? null : (
          <p role="alert" className="text-sm">
            {message}
          </p>
        )}
      </Card>
    </>
  );
}
