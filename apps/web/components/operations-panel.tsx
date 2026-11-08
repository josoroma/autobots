"use client";

import { parseLocalStatus, type LocalStatus } from "@autobots/api-client";
import {
  Activity,
  Archive,
  Box,
  CalendarClock,
  Check,
  CircleAlert,
  Cloud,
  Database,
  HardDrive,
  History,
  Hourglass,
  Layers,
  ListChecks,
  ListOrdered,
  type LucideIcon,
  Network,
  Pause,
  Radio,
  RotateCw,
  Route,
  Server,
  Trash2,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { JobsChart } from "@/components/jobs-chart";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/field";
import { csrfFetch } from "@/lib/csrf-fetch";
import { cn } from "@/lib/utils";

const CONDITIONS: Record<string, string> = {
  database_ready: "The database is answering.",
  database_unreachable: "The database isn't answering. New work is refused.",
  database_not_configured: "No database is configured.",
  schema_ready: "The schema has what this version needs.",
  schema_behind: "Migrations are behind this version. New work is refused.",
  schema_unknown: "The schema can't be checked without the database.",
  no_hold: "Nothing is holding work.",
  restore_hold:
    "This instance was restored. All work is held until an operator releases it.",
  hold_unknown: "Holds can't be checked without the database.",
  adapter_qualified: "The checkpoint adapter is qualified for this release.",
  adapter_unqualified:
    "This release's checkpoint adapter isn't qualified. Saved work and new work wait.",
  adapter_unknown: "The adapter can't be checked without the database.",
  storage_ready: "Storage is answering.",
  storage_unreachable: "Storage isn't answering. New work is refused.",
  storage_not_configured: "No Storage is configured. New work is refused.",
  disk_ready: "The disk has room.",
  disk_low: "The disk is low. New work is refused until there's room.",
  disk_unreadable: "The disk couldn't be checked. New work is refused.",
  queue_ready: "No job has lost its worker.",
  leases_expired: "A job lost its worker. It waits for the next one.",
  worker_ready: "A worker is running.",
  worker_absent: "No worker is running. Queued work waits.",
  no_inference_worker:
    "Queued work needs a worker that can call a model, and none is running.",
};

const LABELS: Record<string, string> = {
  database: "Database",
  schema: "Schema",
  hold: "Hold",
  adapter: "Checkpoints",
  storage: "Storage",
  disk: "Disk",
  queue: "Queue",
  worker: "Worker",
};

// Decorative: each check's name and message carry its meaning.
const ICONS: Record<string, LucideIcon> = {
  database: Database,
  schema: ListChecks,
  hold: Pause,
  adapter: Hourglass,
  storage: Box,
  disk: HardDrive,
  queue: ListOrdered,
  worker: Server,
};

// The dot only repeats the message beside it (Decision 0021 R4).
const DOTS: Record<string, string> = {
  ok: "bg-success-text",
  degraded: "bg-muted-foreground",
  unavailable: "bg-destructive",
};

const BOX = "border-border space-y-3 rounded-xl border px-5 py-4";
const BOX_HEADING = "flex items-center gap-2 text-sm font-semibold";
const HEADING_ICON = "text-muted-foreground size-4 shrink-0";
const FACT_ICON = "text-muted-foreground mt-0.5 size-4 shrink-0";
const RETENTION_ROW =
  "text-muted-foreground flex flex-wrap items-center justify-between gap-x-4 gap-y-1.5 text-[13px]";

const count = new Intl.NumberFormat("en");
const gigabytes = new Intl.NumberFormat("en", { maximumFractionDigits: 1 });

function gb(bytes: number): string {
  return `${gigabytes.format(bytes / 1_000_000_000)} GB`;
}

const HOLD_TEXT: Record<string, string> = {
  no_hold: "no hold",
  restore_hold: "held after a restore",
  hold_unknown: "hold unknown",
};

type Values = LocalStatus["values"];

// PRD-Studio OP-02: a check's measured value, when one exists (Decision 0022 D5). Numbers only.
function valueFor(name: string, values: Values): string | null {
  switch (name) {
    case "database":
      return values.database_p95_ms === null
        ? "No probe timed yet."
        : `p95 ${values.database_p95_ms} ms over the last ${values.database_probes} probes.`;
    case "schema":
      return values.applied_migrations === null
        ? null
        : `${count.format(values.applied_migrations)} migrations applied.`;
    case "adapter":
      // The package and its release. Its name holds the database's, so the page names it plainly.
      return `LangGraph checkpoint adapter ${values.checkpoint_adapter.split(" ").at(-1) ?? ""}.`;
    case "storage":
      return values.storage_bytes === null
        ? null
        : `${count.format(values.storage_bytes)} bytes in published artifacts.`;
    case "disk":
      return values.disk_free_bytes === null || values.disk_total_bytes === null
        ? null
        : `${gb(values.disk_free_bytes)} free of ${gb(values.disk_total_bytes)}.`;
    case "queue":
      return values.leased_jobs === null || values.queued_jobs === null
        ? null
        : `${values.leased_jobs} leased, ${values.queued_jobs} queued.`;
    case "worker":
      return values.workers === null
        ? null
        : `${values.workers} ${values.workers === 1 ? "worker" : "workers"}.`;
    default:
      return null;
  }
}

function days(value: string): number | null {
  const parsed = Number.parseInt(value, 10);
  return Number.isNaN(parsed) ? null : parsed;
}

export function OperationsPanel() {
  const [status, setStatus] = useState<LocalStatus | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [runDays, setRunDays] = useState("");
  const [receiptDays, setReceiptDays] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async (): Promise<void> => {
    const reply = await fetch("/api/v1/operations/local-status", {
      cache: "no-store",
    }).catch(() => null);
    if (reply === null) {
      setFailed("The service didn't answer.");
    } else if (reply.status === 403) {
      setFailed("Only the workspace owner can see Operations.");
    } else if (!reply.ok) {
      setFailed("The service didn't answer.");
    } else {
      const parsed = parseLocalStatus(await reply.json());
      setStatus(parsed);
      setFailed(null);
      setRunDays(parsed.retention?.run_days?.toString() ?? "");
      setReceiptDays(parsed.retention?.receipt_days?.toString() ?? "");
    }
  }, []);

  useEffect(() => {
    let active = true;
    fetch("/api/v1/operations/local-status", { cache: "no-store" })
      .then(async (reply) => {
        if (!active) return;
        if (reply.status === 403) {
          setFailed("Only the workspace owner can see Operations.");
        } else if (!reply.ok) {
          setFailed("The service didn't answer.");
        } else {
          const parsed = parseLocalStatus(await reply.json());
          setStatus(parsed);
          setRunDays(parsed.retention?.run_days?.toString() ?? "");
          setReceiptDays(parsed.retention?.receipt_days?.toString() ?? "");
        }
      })
      .catch(() => {
        if (active) setFailed("The service didn't answer.");
      });
    return () => {
      active = false;
    };
  }, []);

  async function save(): Promise<void> {
    setMessage(null);
    const reply = await csrfFetch("/api/v1/operations/retention", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        run_days: days(runDays),
        receipt_days: days(receiptDays),
      }),
    });
    setMessage(
      reply.ok
        ? "Saved. Nothing is removed until the next retention pass."
        : "Not saved. Retry keys need a run content window at least as short, and windows start at one day.",
    );
    // A refused save keeps what was typed, so it can be corrected.
    if (reply.ok) await load();
  }

  if (failed !== null) return <p role="alert">{failed}</p>;
  if (status === null) return <p role="status">Loading…</p>;
  const passing = status.conditions.filter((item) => item.state === "ok");
  const hold = status.conditions.find((item) => item.name === "hold");
  const workers = status.values.workers;
  return (
    <div className="space-y-5">
      <section
        className={cn(
          "flex flex-wrap items-center gap-4 rounded-xl border px-5 py-4",
          status.ready
            ? "border-success-text/35 dark:bg-success-text/5"
            : "border-destructive/40 dark:bg-destructive/5",
        )}
      >
        <span
          aria-hidden="true"
          className={cn(
            "grid size-9 shrink-0 place-items-center rounded-full border",
            status.ready
              ? "text-success-text border-success-text/35 dark:bg-success-text/15 dark:border-transparent"
              : "text-destructive border-destructive/40 dark:bg-destructive/15 dark:border-transparent",
          )}
        >
          {status.ready ? (
            <Check className="size-4" strokeWidth={2.25} />
          ) : (
            <CircleAlert className="size-4" strokeWidth={2.25} />
          )}
        </span>
        <div className="min-w-0 flex-1 space-y-1">
          <p
            role="status"
            className="font-serif text-[21px] leading-snug tracking-[-0.01em]"
          >
            {status.ready
              ? "Ready. New work can start."
              : "Not ready. New work is refused until this clears."}
          </p>
          {/* OP-01: the counts behind the sentence, from the checks shown below. */}
          <p
            data-field="verdict"
            className="text-muted-foreground text-[13px] tabular-nums"
          >
            <span data-field="checks-passing">
              {passing.length} of {status.conditions.length} checks pass
            </span>
            {" · "}
            <span data-field="workers">
              {workers === null
                ? "workers unknown"
                : `${workers} ${workers === 1 ? "worker" : "workers"}`}
            </span>
            {" · "}
            <span data-field="hold">
              {HOLD_TEXT[hold?.code ?? "hold_unknown"] ?? "hold unknown"}
            </span>
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void load()}>
          <RotateCw aria-hidden="true" />
          Check again
        </Button>
      </section>
      <ul
        data-field="checks"
        className="bg-border border-border grid gap-px overflow-hidden rounded-xl border sm:grid-cols-2 lg:grid-cols-4"
      >
        {status.conditions.map((condition) => {
          const Icon = ICONS[condition.name] ?? Activity;
          return (
            <li
              key={condition.name}
              data-state={condition.state}
              className="bg-background min-h-24 space-y-1.5 px-4 py-3.5"
            >
              <p className="flex items-center gap-2 text-[13.5px] font-semibold">
                <Icon
                  aria-hidden="true"
                  className="text-muted-foreground size-3.5 shrink-0"
                />
                {LABELS[condition.name]}
                <span className="sr-only">: </span>
                <span
                  aria-hidden="true"
                  className={cn(
                    "ml-auto size-1.5 shrink-0 rounded-full",
                    DOTS[condition.state] ?? "bg-muted-foreground",
                  )}
                />
              </p>
              <p className="text-muted-foreground text-[12.5px] leading-relaxed">
                {CONDITIONS[condition.code] ?? condition.code}
              </p>
              {valueFor(condition.name, status.values) === null ? null : (
                <p
                  data-field={`value-${condition.name}`}
                  className="text-foreground text-[12.5px] break-words tabular-nums"
                >
                  {valueFor(condition.name, status.values)}
                </p>
              )}
            </li>
          );
        })}
      </ul>
      <section className="border-border divide-border divide-y rounded-xl border text-sm">
        <p className="flex items-start gap-3 px-4 py-3">
          <Radio aria-hidden="true" className={FACT_ICON} />
          <span>
            Remote tracing:{" "}
            {status.remote_tracing === "disabled"
              ? "off. Logs stay on this Mac."
              : "on. Check this process's environment."}
          </span>
        </p>
        <p className="flex items-start gap-3 px-4 py-3">
          <Archive aria-hidden="true" className={FACT_ICON} />
          <span>
            Last backup:{" "}
            {status.backup_age_hours === null
              ? "none found in the configured directory."
              : `${status.backup_age_hours} hours ago.`}
          </span>
        </p>
        <p data-field="openrouter" className="flex items-start gap-3 px-4 py-3">
          <Cloud aria-hidden="true" className={FACT_ICON} />
          <span>
            OpenRouter:{" "}
            {status.openrouter === "available"
              ? "OpenRouter's catalog answered. That says nothing about your key or a model call."
              : status.openrouter === "unavailable"
                ? "OpenRouter can't be reached. Local work and this page keep working, and new model calls wait."
                : "not checked, as provider settings aren't configured for this process."}
            {status.values.catalog_fetch_ms === null ? null : (
              <span data-field="catalog-time">
                {" "}
                The catalog answered in {status.values.catalog_fetch_ms} ms.
              </span>
            )}
          </span>
        </p>
        <p data-field="loopback" className="flex items-start gap-3 px-4 py-3">
          <Network aria-hidden="true" className={FACT_ICON} />
          <span>
            Network:{" "}
            {status.values.loopback_only === true
              ? "the API listens on this Mac's loopback only."
              : status.values.loopback_only === false
                ? "the API listens beyond loopback. Check how it was started."
                : "not determined in this process."}
          </span>
        </p>
        {status.queue === null ? (
          <p className="flex items-start gap-3 px-4 py-3">
            <Layers aria-hidden="true" className={FACT_ICON} />
            <span>
              Workspace counts need the database, so they aren&apos;t shown.
            </span>
          </p>
        ) : (
          <p className="flex items-start gap-3 px-4 py-3">
            <Layers aria-hidden="true" className={FACT_ICON} />
            <span>
              Jobs in this workspace: {status.queue.queued} queued,{" "}
              {status.queue.claimed} running, {status.queue.expired_leases} lost
              their worker.
            </span>
          </p>
        )}
      </section>
      {status.queue === null ? null : <JobsChart />}
      <div className="grid gap-5 lg:grid-cols-2">
        <section aria-labelledby="delayed-heading" className={BOX}>
          <h2 id="delayed-heading" className={BOX_HEADING}>
            <CalendarClock aria-hidden="true" className={HEADING_ICON} />
            Delayed schedules
          </h2>
          {status.delayed_schedules.length === 0 ? (
            <p data-field="delayed" className="text-muted-foreground text-sm">
              No routine occurrence is recorded as delayed.
            </p>
          ) : (
            <ul
              data-field="delayed"
              className="divide-border divide-y border-t text-sm"
            >
              {status.delayed_schedules.map((occurrence) => (
                <li
                  key={`${occurrence.routine}-${occurrence.occurrence_time}`}
                  className="py-2"
                >
                  {occurrence.routine}: {occurrence.status.replaceAll("_", " ")}{" "}
                  at {new Date(occurrence.occurrence_time).toISOString()}
                  {occurrence.reason === null
                    ? ""
                    : `, ${occurrence.reason.replaceAll("_", " ")}`}
                </li>
              ))}
            </ul>
          )}
        </section>
        <section aria-labelledby="restores-heading" className={BOX}>
          <h2 id="restores-heading" className={BOX_HEADING}>
            <History aria-hidden="true" className={HEADING_ICON} />
            Restore history
          </h2>
          {status.restores.length === 0 ? (
            <p data-field="restores" className="text-muted-foreground text-sm">
              No restore is recorded, so no backup here is known to restore.
            </p>
          ) : (
            <ul
              data-field="restores"
              className="divide-border divide-y border-t text-sm"
            >
              {status.restores.map((restore) => (
                <li key={`${restore.at}-${restore.result}`} className="py-2">
                  {new Date(restore.at).toISOString()}:{" "}
                  {restore.result === "passed"
                    ? `verified, ${restore.checks_passed} of ${restore.checks_total} checks`
                    : restore.result === "failed"
                      ? `verification failed, ${restore.checks_passed} of ${restore.checks_total} checks`
                      : "restored, and not verified"}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
      {status.route_qualifications.length === 0 &&
      status.retention === null ? null : (
        <div className="grid gap-5 lg:grid-cols-2">
          {status.route_qualifications.length === 0 ? null : (
            <section aria-labelledby="routes-heading" className={BOX}>
              <h2 id="routes-heading" className={BOX_HEADING}>
                <Route aria-hidden="true" className={HEADING_ICON} />
                Route qualification
              </h2>
              <ul className="divide-border divide-y border-t text-sm">
                {status.route_qualifications.map((route) => (
                  <li
                    key={route.profile}
                    data-operations-route={route.profile}
                    className="space-y-0.5 py-2.5"
                  >
                    <p className="font-mono text-[12.5px] font-medium break-all">
                      {route.canonical_id}
                    </p>
                    <p>
                      {route.status === "qualified_with_limits"
                        ? `Tested ${route.qualified_on}, with limits.`
                        : "Not qualified."}
                    </p>
                    {route.limits === null ? null : (
                      <p className="text-muted-foreground text-[12.5px] leading-relaxed">
                        {route.limits}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}
          {status.retention === null ? null : (
            <section className={BOX}>
              <h2 className={BOX_HEADING}>
                <Trash2 aria-hidden="true" className={HEADING_ICON} />
                Retention
              </h2>
              <p className="text-muted-foreground text-[13px] leading-relaxed">
                Empty keeps everything. Expiring a finished run removes its
                checkpoints, working files and artifact bytes. Its record,
                activity and operation receipts stay, and a run with an
                unresolved effect is never touched.
              </p>
              <div className="space-y-2.5">
                <label className={RETENTION_ROW}>
                  <span>Run content, days after finishing</span>
                  <Input
                    className="w-28"
                    inputMode="numeric"
                    value={runDays}
                    onChange={(event) => setRunDays(event.target.value)}
                  />
                </label>
                <label className={RETENTION_ROW}>
                  <span>Retry keys, days</span>
                  <Input
                    className="w-28"
                    inputMode="numeric"
                    value={receiptDays}
                    onChange={(event) => setReceiptDays(event.target.value)}
                  />
                </label>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <Button size="sm" onClick={() => void save()}>
                  Save retention
                </Button>
                {message === null ? null : (
                  <p role="status" className="text-sm">
                    {message}
                  </p>
                )}
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
