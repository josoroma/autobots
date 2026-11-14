"use client";

import {
  type ExpertView,
  parseExpertList,
  parseExpertView,
  parseSessionView,
  parseToolCatalog,
  type SessionCreate,
  type ToolDescriptor,
} from "@autobots/api-client";
import { ArrowRight, Plus, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState, type FormEvent } from "react";

import { HeldNote } from "@/components/held-note";
import { Button } from "@/components/ui/button";
import { IconTile } from "@/components/ui/card";
import { Choice, Input } from "@/components/ui/field";
import { SectionLabel } from "@/components/ui/page-header";
import { csrfFetch } from "@/lib/csrf-fetch";
import { formatRelative } from "@/lib/format";
import { PROFILE_NAME } from "@/lib/model-profile";
import { withHeld } from "@/lib/submit";
import { cn } from "@/lib/utils";
import { useSubmit } from "@/lib/use-submit";

const CREATE_REFUSALS: Readonly<Record<string, string>> = {
  owner_required: "Only the workspace owner can create an Expert.",
  expert_name_taken: "That name is already used.",
};
const SESSION_LOST =
  "The reply was lost, so the session may have started. Pressing again won't start a second one.";
const SESSION_REFUSED = "That session could not be started.";
// The coordinator session's target, whose Experts are its body.
const COORDINATOR = "coordinator";

export function ExpertsPanel() {
  // One write at a time, and one key per intent until its outcome is known (Decision 0027 D2).
  const sessions = useSubmit();
  const creates = useSubmit();
  const router = useRouter();
  const [experts, setExperts] = useState<readonly ExpertView[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [name, setName] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [routed, setRouted] = useState<ReadonlySet<string>>(() => new Set());
  const [catalog, setCatalog] = useState<ReadonlyMap<string, ToolDescriptor>>(
    () => new Map(),
  );
  const [filter, setFilter] = useState<Filter>("all");
  const [search, setSearch] = useState("");
  // When the list was read, so each card's last run is measured from then, not during render.
  const [now, setNow] = useState(0);

  useEffect(() => {
    let active = true;
    fetch("/api/v1/experts", { cache: "no-store" })
      .then(async (reply) => {
        if (!active) return;
        if (reply.ok) {
          setExperts(parseExpertList(await reply.json()).experts);
          setNow(Date.now());
        } else setFailed(true);
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    // PRD-Studio EX-02 and EX-03: tool classes and approval come from the catalog.
    fetch("/api/v1/tools", { cache: "no-store" })
      .then(async (reply) => {
        if (!active || !reply.ok) return;
        const tools = parseToolCatalog(await reply.json()).tools;
        setCatalog(new Map(tools.map((tool) => [tool.tool_id, tool])));
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  const classified = useMemo(
    () =>
      (experts ?? []).map((expert) => ({
        expert,
        outside: latestTools(expert).some(
          (tool) =>
            catalog.get(tool)?.operation_class ===
            "consequential_external_write",
        ),
      })),
    [experts, catalog],
  );
  const counts = {
    all: classified.length,
    outside: classified.filter((item) => item.outside).length,
    read_only: classified.filter((item) => !item.outside).length,
  };
  const needle = search.trim().toLowerCase();
  const shown = classified.filter(
    (item) =>
      (filter === "all" ||
        (filter === "outside" ? item.outside : !item.outside)) &&
      (needle === "" || item.expert.name.toLowerCase().includes(needle)),
  );

  async function startRun(expertId: string): Promise<void> {
    const result = await sessions.submit({
      body: () =>
        JSON.stringify({
          kind: "direct",
          experts: [{ expert_id: expertId }],
        } satisfies SessionCreate),
      send: ({ key, body }) =>
        csrfFetch("/api/v1/sessions", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": key,
          },
          body,
        }),
      parse: parseSessionView,
      scope: expertId,
    });
    if (result === null) return;
    if (result.outcome === "accepted" && result.value !== null) {
      router.push(`/sessions/${result.value.id}`);
      return;
    }
    setMessage(
      result.outcome === "unknown"
        ? SESSION_LOST
        : withHeld(SESSION_REFUSED, result.held),
    );
  }

  async function create(event: FormEvent): Promise<void> {
    event.preventDefault();
    setMessage(null);
    const result = await creates.submit({
      body: () => JSON.stringify({ name, config: {} }),
      send: ({ key, body }) =>
        csrfFetch("/api/v1/experts", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": key,
          },
          body,
        }),
      parse: parseExpertView,
    });
    if (result === null) return;
    if (result.outcome === "accepted" && result.value !== null) {
      router.push(`/experts/${result.value.id}`);
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

  async function coordinate(): Promise<void> {
    const result = await sessions.submit({
      body: () =>
        JSON.stringify({
          kind: "coordinator",
          experts: [...routed].map((expert_id) => ({ expert_id })),
        } satisfies SessionCreate),
      send: ({ key, body }) =>
        csrfFetch("/api/v1/sessions", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": key,
          },
          body,
        }),
      parse: parseSessionView,
      scope: COORDINATOR,
    });
    if (result === null) return;
    if (result.outcome === "accepted" && result.value !== null) {
      router.push(`/sessions/${result.value.id}`);
      return;
    }
    setMessage(
      result.outcome === "unknown"
        ? SESSION_LOST
        : withHeld(SESSION_REFUSED, result.held),
    );
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
  // While a coordinator session is held, the Experts it names stay as sent (Decision 0027 D2).
  const routing = sessions.holding(COORDINATOR);
  return (
    <>
      <section aria-labelledby="list-heading" className="space-y-4">
        <SectionLabel id="list-heading">Your Experts</SectionLabel>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div
            role="group"
            aria-label="Show"
            className="bg-muted/60 inline-flex w-fit flex-wrap gap-0.5 rounded-lg p-[3px]"
          >
            {FILTERS.map(([id, label]) => (
              <button
                key={id}
                type="button"
                data-filter={id}
                aria-pressed={filter === id}
                onClick={() => setFilter(id)}
                className={cn(
                  "text-foreground/80 inline-flex h-7 items-center gap-1.5 rounded-md border border-transparent px-3 text-[13px]",
                  filter === id &&
                    "bg-background text-foreground border-border font-medium dark:bg-accent",
                )}
              >
                {label} <span className="tabular-nums">{counts[id]}</span>
              </button>
            ))}
          </div>
          <span className="hidden flex-1 sm:block" />
          <label className="block">
            <span className="sr-only">Search Experts</span>
            <Input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search Experts"
              className="h-8 w-full sm:w-60"
            />
          </label>
        </div>
        {experts.length === 0 ? (
          <p className="text-muted-foreground rounded-xl border border-dashed p-6 text-sm">
            No Experts yet.
          </p>
        ) : shown.length === 0 ? (
          <p className="text-muted-foreground rounded-xl border border-dashed p-6 text-sm">
            No Experts match.
          </p>
        ) : (
          <ul className="grid gap-3.5 @xl:grid-cols-2 @4xl:grid-cols-3">
            {shown.map(({ expert }) => (
              <ExpertCard
                key={expert.id}
                expert={expert}
                catalog={catalog}
                now={now}
                checked={routed.has(expert.id)}
                locked={routing}
                busy={sessions.pending}
                onToggle={() => toggle(expert.id)}
                onStart={() => void startRun(expert.id)}
              />
            ))}
          </ul>
        )}
        <div className="flex flex-wrap items-center justify-end gap-3">
          {routing ? <HeldNote /> : null}
          <Button
            className="rounded-full"
            onClick={() => void coordinate()}
            disabled={routed.size === 0 || sessions.pending}
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
          <p role="alert" data-message="create" className="text-sm">
            {message}
          </p>
        )}
      </section>
    </>
  );
}

const SHOWN_TOOLS = 4;

type Filter = "all" | "outside" | "read_only";
const FILTERS: [Filter, string][] = [
  ["all", "All"],
  ["outside", "Can change things outside"],
  ["read_only", "Read only"],
];
// The noun each always-approved tool decides on, for "Approval on every issue".
const APPROVAL_NOUN: Record<string, string> = {
  create_github_issue: "issue",
  github_open_pull_request: "pull request",
};

function latestTools(expert: ExpertView): readonly string[] {
  return expert.versions.at(-1)?.config.tools ?? [];
}

// One Expert as a card: what its latest version says, from the list already loaded.
function ExpertCard({
  expert,
  catalog,
  now,
  checked,
  locked,
  busy,
  onToggle,
  onStart,
}: {
  expert: ExpertView;
  catalog: ReadonlyMap<string, ToolDescriptor>;
  /** When the list was read, in epoch milliseconds. */
  now: number;
  checked: boolean;
  // A held coordinator session names these Experts, so they stay as sent.
  locked: boolean;
  busy: boolean;
  onToggle: () => void;
  onStart: () => void;
}) {
  const latest = expert.versions.at(-1)?.config;
  const executor = latest?.role_bindings?.executor;
  const approvals = (latest?.tools ?? []).filter(
    (tool) => catalog.get(tool)?.approval === "always",
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
          <p
            data-field="role"
            className="text-muted-foreground font-mono text-[11.5px] wrap-anywhere"
          >
            executor ·{" "}
            {executor === undefined
              ? "Workspace default"
              : PROFILE_NAME[executor]}{" "}
            · version {expert.latest_version}
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="shrink-0"
          disabled={busy}
          onClick={onStart}
        >
          Start run
          <span className="sr-only"> with {expert.name}</span>
        </Button>
        <Choice
          type="checkbox"
          id={`route-${expert.id}`}
          checked={checked}
          disabled={locked}
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
      <p data-field="runs" className="text-muted-foreground text-[12.5px]">
        {expert.run_count === 0
          ? "No runs yet"
          : `${expert.run_count} ${expert.run_count === 1 ? "run" : "runs"}${
              expert.last_run_at === null
                ? ""
                : ` · last run ${formatRelative(expert.last_run_at, now)}`
            }`}
      </p>
      {approvals.length === 0 ? null : (
        <p
          data-field="approval"
          className="text-attention flex items-center gap-1.5 text-[12.5px]"
        >
          <ShieldAlert aria-hidden="true" className="size-3.5" />
          Approval on every{" "}
          {approvals.length === 1
            ? (APPROVAL_NOUN[approvals[0] ?? ""] ?? "call")
            : "call to these tools"}
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
