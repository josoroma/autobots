"use client";

import { parseLocalStatus, type LocalStatus } from "@autobots/api-client";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { csrfFetch } from "@/lib/csrf-fetch";

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
  return (
    <div className="space-y-4">
      <Card className="space-y-3 p-4">
        <p role="status" className="font-medium">
          {status.ready
            ? "Ready. New work can start."
            : "Not ready. New work is refused until this clears."}
        </p>
        <ul className="space-y-1 text-sm">
          {status.conditions.map((condition) => (
            <li key={condition.name} data-state={condition.state}>
              <span className="font-medium">{LABELS[condition.name]}: </span>
              {CONDITIONS[condition.code] ?? condition.code}
            </li>
          ))}
        </ul>
        <p className="text-sm">
          Remote tracing:{" "}
          {status.remote_tracing === "disabled"
            ? "off. Logs stay on this Mac."
            : "on. Check this process's environment."}
        </p>
        <p className="text-sm">
          Last backup:{" "}
          {status.backup_age_hours === null
            ? "none found in the configured directory."
            : `${status.backup_age_hours} hours ago.`}
        </p>
        {status.queue === null ? (
          <p className="text-sm">
            Workspace counts need the database, so they aren&apos;t shown.
          </p>
        ) : (
          <p className="text-sm">
            Jobs in this workspace: {status.queue.queued} queued,{" "}
            {status.queue.claimed} running, {status.queue.expired_leases} lost
            their worker.
          </p>
        )}
        <Button variant="secondary" onClick={() => void load()}>
          Check again
        </Button>
      </Card>
      {status.retention === null ? null : (
        <Card className="space-y-3 p-4">
          <h2 className="font-medium">Retention</h2>
          <p className="text-sm">
            Empty keeps everything. Expiring a finished run removes its
            checkpoints, working files and artifact bytes. Its record, activity
            and operation receipts stay, and a run with an unresolved effect is
            never touched.
          </p>
          <label className="block text-sm">
            Run content, days after finishing
            <input
              className="ml-2 w-24 rounded border px-2 py-1"
              inputMode="numeric"
              value={runDays}
              onChange={(event) => setRunDays(event.target.value)}
            />
          </label>
          <label className="block text-sm">
            Retry keys, days
            <input
              className="ml-2 w-24 rounded border px-2 py-1"
              inputMode="numeric"
              value={receiptDays}
              onChange={(event) => setReceiptDays(event.target.value)}
            />
          </label>
          <Button onClick={() => void save()}>Save retention</Button>
          {message === null ? null : <p role="status">{message}</p>}
        </Card>
      )}
    </div>
  );
}
