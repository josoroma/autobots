# Runbook: local operations

Starting, draining, stopping and reading the health of the local stack, and applying retention.

**Last exercised:** on a disposable Compose project by `python3.12 scripts/qualify_operations.py`, which runs this procedure with a scripted model and writes `.checks/operations/qualification.json`. It has **not** been run on a persistent stack: none is configured on this machine, because the proposed ports `54321` and `54322` belong to another project. The commands below are the ones qualified, with the persistent project's name and env file still to be chosen.

## Prerequisites and target

- `PROJECT` is the Compose project you mean to touch. Check it first. Never run these against another project on this Mac.
- Docker with the pinned images, the prepared `services/agent/.venv`, and an env file holding the values in [the local app runbook](local-app.md). No secret goes on a command line or into a log.
- Named volumes hold the data. Nothing here removes them. `docker compose down -v`, `docker volume rm`, `docker system prune` and a database reset are not part of any routine step.

## Start

In this order, as LM-07 states.

```sh
docker compose -p "$PROJECT" --env-file "$ENV_FILE" -f infra/supabase/upstream/docker-compose.yml -f infra/supabase/compose.overlay.yaml up -d --wait --wait-timeout 240
```

Then apply reviewed migrations with the migration role. The guarded persistent apply isn't implemented yet: `scripts/app_db.py` refuses anything but a disposable target, so a persistent apply is an explicit step for whoever owns that stack. Then start the processes:

```sh
services/agent/.venv/bin/python -m uvicorn --factory autobots.api.main:create_configured_app --host 127.0.0.1 --port 8001 --no-access-log 2>> "$LOG_DIR/api.log"
services/agent/.venv/bin/python -m autobots.operations.worker 2>> "$LOG_DIR/worker.log"
```

Expected: `GET /v1/operations/local-status`, or the Operations page, says ready. Until then, `POST /v1/runs` and starting a workflow answer `503 not_ready`, and nothing is queued.

## What the worker does today

`autobots.operations.worker` expires approvals, evaluates routines and applies retention. **It doesn't claim jobs**, because it has no model client until inference is qualified (US-3.4). Queued runs wait, and Operations says `no_inference_worker`. The goal loop itself has only run under a scripted model.

## Reading health

| Condition | Code | Admission | What to do |
|---|---|---|---|
| Database | `database_unreachable` | refused | `docker compose -p "$PROJECT" ps db`. The API reconnects by itself once it's back. |
| Schema | `schema_behind` | refused | Apply the pending migrations. |
| Storage | `storage_unreachable` | refused | `docker compose -p "$PROJECT" ps storage`, then `start storage`. |
| Disk | `disk_low` | refused | Free space, or lower `AUTOBOTS_MIN_FREE_BYTES` (default 2 GiB). This is the host disk. Docker's VM disk has its own limit and isn't measured. |
| Queue | `leases_expired` | allowed | A worker stopped mid-job. The next inference worker takes it. |
| Worker | `worker_absent`, `no_inference_worker` | allowed | Queued work waits. Start a worker. |
| Hold | `restore_hold` | refused | This is a restored instance. See [the backup and restore runbook](backup-restore.md). |

With the database down the page still answers, with `scope: installation` and no workspace counts. Only an owner sees it while the database is up.

Logs are JSON lines on stderr, kept in `$LOG_DIR` on this Mac. Secret shapes are replaced with `[redacted]` and identifiers are cut to eight characters. An exception logs its type, never its message. uvicorn's own start and stop lines are plain text. API and worker bootstrap turn inherited LangSmith and OTLP settings off, and Operations reports it.

## Drain and stop

In this order: web and API first so nothing new is admitted, then the worker, then containers.

```sh
kill -TERM "$WEB_PID"
kill -TERM "$API_PID"
kill -TERM "$WORKER_PID"
docker compose -p "$PROJECT" stop
```

Expected: the worker's heartbeat goes to `draining` then `stopped`, and it logs `worker.draining` and `worker.stopped`. A step finishes if it can within `AUTOBOTS_WORKER_DRAIN_SECONDS` (default 30). uvicorn exits with status -15 after `Application shutdown complete`, which is its normal clean stop.

**If the drain runs out:** the worker logs `worker.drain_cut_short` and exits. The job's lease expires, and Operations shows `leases_expired`. A model call in flight at that moment may have been charged, so the run pauses with `uncertain_model_call` instead of retrying. Look up the charge in OpenRouter's own records, then reconcile it and resume:

1. `POST /v1/runs/{run_id}/model-calls/reconcile` with `{"charged_micro_usd": <what the provider recorded>}`
2. `POST /v1/runs/{run_id}/resume`

Resume needs a usable key. The disposable exercise has none, so it calls the same command directly, and the route's key check was not exercised there.

## Retention

Set per workspace on the Operations page, or with `PUT /v1/operations/retention`. No window means keep everything, and that's the default. The worker applies it hourly, and an owner can run `POST /v1/operations/retention/apply`.

| After | Removed | Kept |
|---|---|---|
| `run_days` past a run finishing | Checkpoints, working files, offloads, summaries, artifact bytes (the row reads `expired`) | Run record, goal text, events, evidence, every tool receipt |
| `receipt_days` | Idempotency keys, so a retry past it is treated as new | Keys for active runs, and every tool receipt |

`receipt_days` can't be shorter than `run_days`. A run is refused, and retried on the next pass, while its tree is active, a continuation of it is active, it has a `started` or `unknown` tool receipt, or an obligation is open. Purges are recorded in `app_private.retention_log`. If Storage is down, rows commit and bytes wait for the next pass.

A purged run has no explanation on its page yet: its artifacts just aren't listed.

## Backup and restore

See [the backup and restore runbook](backup-restore.md).

## Failure symptoms

- **`503 not_ready` with everything apparently up:** read the conditions. A disk below the minimum refuses admission on its own.
- **Queued forever:** expected until an inference worker exists.
- **A run paused after a restart:** read its reason. An uncertain call or unknown effect is waiting for a person, not stuck.

## Cleanup

Nothing here creates anything to clean up. `scripts/qualify_operations.py` removes only its own `autobots-disposable-*` project, and its logs go to the ignored `.checks/operations/logs`.
