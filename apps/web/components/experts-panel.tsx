"use client";

import {
  parseExpertList,
  parseExpertView,
  type ExpertView,
} from "@autobots/api-client";
import { ArrowRight, Plus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { IconTile } from "@/components/ui/card";
import { Choice, Input } from "@/components/ui/field";
import { SectionLabel } from "@/components/ui/page-header";
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
      <p role="status" className="text-muted-foreground text-sm">
        Loading Experts.
      </p>
    );
  }
  return (
    <>
      <section aria-labelledby="list-heading" className="space-y-4">
        <SectionLabel id="list-heading">Your Experts</SectionLabel>
        {experts.length === 0 ? (
          <p className="text-muted-foreground rounded-xl border border-dashed p-6 text-sm">
            No Experts yet.
          </p>
        ) : (
          <ul className="grid gap-3.5 @xl:grid-cols-2 @4xl:grid-cols-3">
            {experts.map((expert) => (
              <ExpertCard
                key={expert.id}
                expert={expert}
                checked={routed.has(expert.id)}
                onToggle={() => toggle(expert.id)}
              />
            ))}
          </ul>
        )}
        <div className="flex justify-end">
          <Button
            className="rounded-full"
            onClick={() => void coordinate()}
            disabled={routed.size === 0}
          >
            Start a coordinator session
            <ArrowRight aria-hidden="true" />
          </Button>
        </div>
      </section>
      <section
        aria-labelledby="create-heading"
        className="space-y-3 rounded-xl border border-dashed p-5"
      >
        <div className="flex items-center gap-3">
          <IconTile icon={Plus} className="rounded-full" />
          <h2 id="create-heading" className="text-[15px] font-semibold">
            New Expert
          </h2>
        </div>
        <form
          onSubmit={(event) => void create(event)}
          className="flex flex-col gap-3 sm:flex-row sm:items-end"
        >
          <div className="min-w-0 flex-1 space-y-1.5 sm:max-w-sm">
            <label htmlFor="expert-name" className="text-sm font-medium">
              Name
            </label>
            <Input
              id="expert-name"
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
          <p role="alert" data-message="create" className="text-sm">
            {message}
          </p>
        )}
      </section>
    </>
  );
}

const SHOWN_TOOLS = 4;

// One Expert as a card: what its latest version says, from the list already loaded.
function ExpertCard({
  expert,
  checked,
  onToggle,
}: {
  expert: ExpertView;
  checked: boolean;
  onToggle: () => void;
}) {
  const latest = expert.versions.at(-1)?.config;
  const bindings = Object.entries(latest?.role_bindings ?? {}).map(
    ([role, profile]) => `${role}: ${String(profile)}`,
  );
  const tools = latest?.tools ?? [];
  const groups = latest?.tool_groups ?? [];
  const purpose = latest?.purpose?.trim() ?? "";
  return (
    <li className="bg-card text-card-foreground has-checked:border-primary/60 has-checked:ring-primary/15 flex flex-col gap-3 rounded-xl border p-[18px] has-checked:ring-3">
      <div className="flex items-start gap-3">
        <span
          aria-hidden="true"
          className="bg-background grid size-9 shrink-0 place-items-center rounded-[10px] border font-serif text-base dark:border-transparent dark:bg-muted"
        >
          {expert.name.trim().charAt(0).toUpperCase()}
        </span>
        <div className="min-w-0 flex-1">
          <Link
            href={`/experts/${expert.id}`}
            className="text-[15px] font-semibold wrap-anywhere underline-offset-4 hover:underline"
          >
            {expert.name}
          </Link>
          <p className="text-muted-foreground font-mono text-[11.5px] wrap-anywhere">
            <span>Version {expert.latest_version}</span>
            {bindings.length === 0 ? null : (
              <span> · {bindings.join(", ")}</span>
            )}
          </p>
        </div>
        <Choice
          type="checkbox"
          id={`route-${expert.id}`}
          checked={checked}
          onChange={onToggle}
          aria-label={`Include ${expert.name} in a coordinator session`}
          className="mt-0.5 shrink-0"
        />
      </div>
      {purpose === "" ? null : (
        <p className="text-muted-foreground text-[13.5px] leading-normal">
          {purpose}
        </p>
      )}
      <div className="mt-auto flex flex-wrap gap-1.5 border-t pt-3">
        {tools.length === 0 && groups.length === 0 ? (
          <span className={CHIP}>no tools</span>
        ) : (
          <>
            {tools.slice(0, SHOWN_TOOLS).map((tool) => (
              <span key={tool} className={CHIP}>
                {tool}
              </span>
            ))}
            {tools.length > SHOWN_TOOLS ? (
              <span className={CHIP}>+{tools.length - SHOWN_TOOLS}</span>
            ) : null}
            {groups.length === 0 ? null : (
              <span className={CHIP}>groups: {groups.join(", ")}</span>
            )}
          </>
        )}
      </div>
    </li>
  );
}

const CHIP =
  "text-muted-foreground rounded-md border px-1.5 py-px font-mono text-[11.5px] wrap-anywhere";
