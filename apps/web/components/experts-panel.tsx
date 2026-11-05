"use client";

import {
  parseExpertList,
  parseExpertView,
  type ExpertView,
} from "@autobots/api-client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { csrfFetch } from "@/lib/csrf-fetch";

export function ExpertsPanel() {
  const router = useRouter();
  const [experts, setExperts] = useState<readonly ExpertView[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [name, setName] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [routed, setRouted] = useState<ReadonlySet<string>>(() => new Set());

  useEffect(() => {
    let active = true;
    fetch("/api/v1/experts", { cache: "no-store" })
      .then(async (reply) => {
        if (!active) return;
        if (reply.ok) setExperts(parseExpertList(await reply.json()).experts);
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
    const reply = await csrfFetch("/api/v1/experts", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": crypto.randomUUID(),
      },
      body: JSON.stringify({ name, config: {} }),
    }).catch(() => null);
    if (reply?.ok === true) {
      router.push(`/experts/${parseExpertView(await reply.json()).id}`);
      return;
    }
    const failure = (await reply?.json().catch(() => null)) as {
      code?: string;
    } | null;
    setMessage(
      failure?.code === "owner_required"
        ? "Only the workspace owner can create an Expert."
        : failure?.code === "expert_name_taken"
          ? "That name is already used."
          : "That could not be saved.",
    );
  }

  async function coordinate(): Promise<void> {
    const reply = await csrfFetch("/api/v1/sessions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": crypto.randomUUID(),
      },
      body: JSON.stringify({
        kind: "coordinator",
        experts: [...routed].map((expert_id) => ({ expert_id })),
      }),
    }).catch(() => null);
    if (reply?.ok === true) {
      const session = (await reply.json()) as { id: string };
      router.push(`/sessions/${session.id}`);
    } else {
      setMessage("That session could not be started.");
    }
  }

  function toggle(id: string): void {
    setRouted((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  if (failed) {
    return (
      <p role="alert" className="text-sm">
        Experts could not be loaded. Sign in, then try again.
      </p>
    );
  }
  if (experts === null) {
    return (
      <p role="status" className="text-sm">
        Loading Experts.
      </p>
    );
  }
  return (
    <>
      <Card aria-labelledby="list-heading" className="space-y-3">
        <h2 id="list-heading" className="text-lg font-medium">
          Your Experts
        </h2>
        {experts.length === 0 ? (
          <p className="text-sm">No Experts yet.</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {experts.map((expert) => (
              <li key={expert.id} className="flex items-center gap-3">
                <input
                  type="checkbox"
                  id={`route-${expert.id}`}
                  checked={routed.has(expert.id)}
                  onChange={() => toggle(expert.id)}
                  aria-label={`Include ${expert.name} in a coordinator session`}
                />
                <Link
                  href={`/experts/${expert.id}`}
                  className="font-medium underline"
                >
                  {expert.name}
                </Link>
                <span className="text-muted-foreground">
                  Version {expert.latest_version}
                </span>
              </li>
            ))}
          </ul>
        )}
        <Button
          variant="secondary"
          onClick={() => void coordinate()}
          disabled={routed.size === 0}
        >
          Start a coordinator session
        </Button>
      </Card>
      <Card aria-labelledby="create-heading" className="space-y-3">
        <h2 id="create-heading" className="text-lg font-medium">
          New Expert
        </h2>
        <form onSubmit={(event) => void create(event)} className="space-y-3">
          <label htmlFor="expert-name" className="text-sm font-medium">
            Name
          </label>
          <input
            id="expert-name"
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
          <p role="alert" data-message="create" className="text-sm">
            {message}
          </p>
        )}
      </Card>
    </>
  );
}
