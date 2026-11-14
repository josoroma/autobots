"use client";

import { parseRunList, type RunList as Runs } from "@autobots/api-client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { RunPanel } from "@/components/run-panel";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/field";
import { LoadEmpty, LoadState } from "@/components/ui/load-state";
import { PageHeader } from "@/components/ui/page-header";
import { loadJson, type LoadFailure } from "@/lib/load";
import { useResource } from "@/lib/use-resource";
import { cn } from "@/lib/utils";

export const STATUS_TEXT: Record<string, string> = {
  queued: "Queued",
  running: "Running",
  waiting_input: "Waiting for input",
  waiting_approval: "Waiting for approval",
  paused: "Paused",
  verifying: "Verifying",
  cancelling: "Cancelling",
  succeeded: "Succeeded",
  failed: "Failed",
  cancelled: "Cancelled",
};

// Decision 0021 R3–R4: the dot repeats the state's words, never replaces them. What runs is live,
// what waits for a person takes the attention tone, a failure is destructive; the rest stay neutral.
type Tone = "live" | "attention" | "success" | "failure" | "idle";

const TONES: Record<string, Tone> = {
  running: "live",
  verifying: "live",
  waiting_input: "attention",
  waiting_approval: "attention",
  succeeded: "success",
  failed: "failure",
};

function tone(status: string): Tone {
  return TONES[status] ?? "idle";
}

const STATE_TEXT: Record<Tone, string> = {
  live: "text-live-text",
  attention: "text-attention",
  success: "text-foreground",
  failure: "text-destructive",
  idle: "text-foreground",
};

const STATE_DOT: Record<Tone, string> = {
  live: "bg-live-text ring-live-text/20 ring-[3px]",
  attention: "bg-attention",
  success: "bg-success-text",
  failure: "bg-destructive",
  idle: "border-muted-foreground border-[1.5px]",
};

const COLUMNS = "lg:grid-cols-[minmax(0,1fr)_12rem_7rem_9rem_9rem] lg:gap-x-5";

type Group = "all" | "active" | "needs_you" | "finished";
const GROUPS: { id: Group; label: string }[] = [
  { id: "all", label: "All" },
  { id: "active", label: "Active" },
  { id: "needs_you", label: "Needs you" },
  { id: "finished", label: "Finished" },
];
const PROFILE_NAMES: Record<string, string> = {
  openrouter_terra: "Terra",
  openrouter_sol: "Sol",
  openrouter_deepseek_flash: "DeepSeek Flash",
};
const STOP_TEXT: Record<string, string> = {
  tool_budget_exceeded: "tool budget",
  budget_exhausted: "budget",
};

type Row = Runs["runs"][number];

function dollars(micro: number): string {
  return `US$${(micro / 1_000_000).toFixed(2)}`;
}

// PRD-Studio RN-03: "≈" while a reservation is outstanding or a charge went unreported.
function Spend({ run }: { run: Row }) {
  const estimated = run.reserved_micro_usd > 0 || run.unreported;
  const spent = run.charged_micro_usd + run.reserved_micro_usd;
  const share =
    run.limit_micro_usd > 0
      ? Math.min(100, Math.round((spent / run.limit_micro_usd) * 100))
      : 0;
  return (
    <span data-field="spend" className="block lg:text-right">
      <span className="tabular-nums">
        {estimated ? (
          <>
            <span aria-hidden="true">≈ </span>
            <span className="sr-only">About </span>
          </>
        ) : null}
        {dollars(spent)}
      </span>
      <span className="text-muted-foreground block text-xs tabular-nums">
        {estimated ? "estimated, " : ""}of {dollars(run.limit_micro_usd)}
      </span>
      <span
        aria-hidden="true"
        className="bg-muted mt-1 block h-1 w-full overflow-hidden rounded-full lg:ml-auto lg:w-24"
      >
        <span
          className="bg-foreground/70 block h-full rounded-full"
          style={{ width: `${share}%` }}
        />
      </span>
    </span>
  );
}

// The state's dot and words, for a row and for the side panel.
export function StateLine({ status, text }: { status: string; text?: string }) {
  return (
    <span
      data-field="state"
      className={cn(
        "inline-flex items-center gap-2 text-[13px]",
        STATE_TEXT[tone(status)],
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          "size-[7px] shrink-0 rounded-full",
          STATE_DOT[tone(status)],
        )}
      />
      {text ?? STATUS_TEXT[status] ?? status}
    </span>
  );
}

function stateLine(run: Row): string {
  const words = STATUS_TEXT[run.status] ?? run.status;
  if (run.status === "failed" && run.stop_reason)
    return `${words} · ${STOP_TEXT[run.stop_reason] ?? run.stop_reason.replaceAll("_", " ")}`;
  if (
    (run.status === "running" || run.status === "verifying") &&
    run.tasks_total > 0
  )
    return `${words} · ${run.tasks_complete} of ${run.tasks_total}`;
  return words;
}

// What Load more added to one first page: its rows, the newest page and why the last read failed. A
// newer first page replaces it, so a page read for older filters is never appended to newer ones.
interface More {
  base: Runs;
  runs: Row[];
  next: Runs | null;
  failure: LoadFailure | null;
  loading: boolean;
}

function withMore(base: Runs, more: More | null): Runs {
  return more?.next == null
    ? base
    : { ...more.next, runs: [...base.runs, ...more.runs] };
}

export function RunList() {
  const [group, setGroup] = useState<Group>("all");
  const [query, setQuery] = useState("");
  const [profile, setProfile] = useState("");
  const [more, setMore] = useState<More | null>(null);
  // RN-04: the selected run's panel, in the address so a reload keeps it open.
  const selected = useSearchParams().get("run");
  // Defaults send no query string, so the first load is plain /api/v1/runs.
  const path = (cursor: string | null) => {
    const params = new URLSearchParams();
    if (group !== "all") params.set("group", group);
    if (query.trim() !== "") params.set("q", query.trim());
    if (profile !== "") params.set("profile", profile);
    if (cursor !== null) params.set("cursor", cursor);
    const search = params.toString();
    return search === "" ? "/api/v1/runs" : `/api/v1/runs?${search}`;
  };
  // Typing in the filter sends one read once it pauses.
  const { state, pending, reload } = useResource(path(null), parseRunList, {
    delayMs: 150,
  });
  const base = state.kind === "ready" ? state.value : null;
  const shown = more?.base === base ? more : null;
  const list = base === null ? null : withMore(base, shown);

  async function loadMore(): Promise<void> {
    if (base === null || list?.next_cursor == null) return;
    const kept = shown ?? { base, runs: [], next: null, failure: null };
    setMore({ ...kept, loading: true });
    const loaded = await loadJson(path(list.next_cursor), parseRunList);
    setMore(
      loaded.kind === "ready"
        ? {
            base,
            runs: [...kept.runs, ...loaded.value.runs],
            next: loaded.value,
            failure: null,
            loading: false,
          }
        : { ...kept, failure: loaded, loading: false },
    );
  }

  return (
    <div className="max-w-6xl space-y-5">
      <PageHeader
        title="Runs"
        description="Every goal started on this Mac, from queued to finished. A finished run can't resume; start a similar one instead."
      />
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
        <div
          role="group"
          aria-label="Status"
          className="bg-muted/60 inline-flex w-fit flex-wrap gap-0.5 rounded-lg p-[3px]"
        >
          {GROUPS.map((item) => (
            <button
              key={item.id}
              type="button"
              aria-pressed={group === item.id}
              data-group={item.id}
              onClick={() => setGroup(item.id)}
              className={cn(
                "text-foreground/80 inline-flex h-7 items-center gap-1.5 rounded-md border border-transparent px-3 text-[13px]",
                group === item.id &&
                  "bg-background text-foreground border-border font-medium dark:bg-accent",
              )}
            >
              {item.label}{" "}
              <span className="tabular-nums">
                {list === null ? "" : list.counts[item.id]}
              </span>
            </button>
          ))}
        </div>
        <span className="hidden flex-1 lg:block" />
        <label className="flex items-center gap-2 text-[13px]">
          <span className="sr-only">Filter by goal or Expert</span>
          <Input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Filter by goal or Expert"
            className="h-8 w-full lg:w-64"
          />
        </label>
        <label className="flex items-center gap-2 text-[13px]">
          <span className="text-muted-foreground">Model</span>
          <Select
            value={profile}
            onChange={(event) => setProfile(event.target.value)}
            className="h-8 w-40"
          >
            <option value="">Any model</option>
            {Object.entries(PROFILE_NAMES).map(([id, name]) => (
              <option key={id} value={id}>
                {name}
              </option>
            ))}
          </Select>
        </label>
      </div>
      {list === null ? (
        <LoadState
          state={state}
          what="runs"
          onRetry={reload}
          pending={pending}
        />
      ) : (
        <Listed
          list={list}
          more={shown}
          selected={selected}
          onMore={() => void loadMore()}
        />
      )}
      {selected === null ? null : (
        <RunPanel key={selected} runId={selected} onChanged={reload} />
      )}
    </div>
  );
}

function Listed({
  list,
  more,
  selected,
  onMore,
}: {
  list: Runs;
  more: More | null;
  selected: string | null;
  onMore: () => void;
}) {
  const router = useRouter();
  if (list.runs.length === 0) {
    return (
      <Card className="border-dashed">
        <LoadEmpty>
          {list.counts.all === 0 ? (
            <>
              This workspace has no runs yet. Start one from{" "}
              <Link href="/" className="font-medium underline">
                Home
              </Link>
              .
            </>
          ) : (
            "No runs match these filters."
          )}
        </LoadEmpty>
      </Card>
    );
  }
  return (
    <div>
      {/* Column names for sighted readers; each row says its own facts in words. */}
      <div
        aria-hidden="true"
        className={cn(
          COLUMNS,
          "text-muted-foreground hidden border-b px-3 pb-2.5 text-[12.5px] font-medium lg:grid",
        )}
      >
        <span>Goal</span>
        <span>State</span>
        <span>Models</span>
        <span className="text-right">Spend</span>
        <span className="text-right">Started</span>
      </div>
      <ul className="divide-border divide-y border-b text-[13.5px] max-lg:border-t">
        {list.runs.map((run) => (
          <li
            key={run.id}
            data-run={run.id}
            data-status={run.status}
            className={cn(
              COLUMNS,
              "grid gap-x-6 gap-y-1.5 px-3 py-3 lg:min-h-[56px] lg:items-center lg:py-2",
            )}
          >
            <div className="min-w-0">
              <Link
                href={`/runs/${run.id}`}
                className="text-foreground font-medium break-words underline-offset-4 hover:underline"
              >
                {run.goal_summary === "" ? "Untitled run" : run.goal_summary}
              </Link>
              <span
                data-field="label"
                className="text-muted-foreground mt-0.5 block text-xs"
              >
                {run.label ?? "Goal"}
                {run.parent_run_id === null ? null : " · A child run"}
                {" · "}
                <button
                  type="button"
                  onClick={() =>
                    router.replace(`/runs?run=${encodeURIComponent(run.id)}`, {
                      scroll: false,
                    })
                  }
                  aria-expanded={run.id === selected}
                  aria-controls={run.id === selected ? "run-panel" : undefined}
                  aria-label={`Details for ${run.goal_summary === "" ? "Untitled run" : run.goal_summary}`}
                  data-field="details"
                  className="text-foreground underline underline-offset-4"
                >
                  Details
                </button>
              </span>
            </div>
            <StateLine status={run.status} text={stateLine(run)} />
            <span
              data-field="models"
              className="text-muted-foreground font-mono text-xs"
            >
              <span className="lg:sr-only">Models </span>
              {run.profiles.length === 0
                ? "—"
                : run.profiles
                    .map((item) => PROFILE_NAMES[item] ?? item)
                    .join(" · ")}
            </span>
            <Spend run={run} />
            <span className="text-muted-foreground tabular-nums lg:text-right">
              <span className="lg:sr-only">Started </span>
              {new Date(run.created_at).toISOString()}
            </span>
          </li>
        ))}
      </ul>
      <div className="mt-4 flex items-center gap-3 text-[12.5px]">
        <span data-state="shown" className="text-muted-foreground">
          Showing {list.runs.length} of {list.total}
        </span>
        <span className="flex-1" />
        {list.has_more ? (
          <Button
            variant="outline"
            size="sm"
            disabled={more?.loading === true}
            onClick={onMore}
          >
            Load more
          </Button>
        ) : null}
      </div>
      {more?.failure == null ? null : (
        <LoadState state={more.failure} what="more runs" className="mt-3" />
      )}
    </div>
  );
}
