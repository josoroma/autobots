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

`autobots.operations.worker` expires approvals, evaluates routines and applies retention. **By default it doesn't claim jobs**, because claiming spends real money. Queued runs wait, and Operations says `no_inference_worker`.

## Turning on inference

**This spends real money once a key exists: every queued run in every workspace with a key sends billed requests to OpenRouter.** Both routes have met the real provider ([with their limits](../evidence/US-3.4/summary.md)). [One goal, repeated on disposable stacks,](../evidence/LIVE-GOAL-1/summary.md) went Terra 5 of 5 and DeepSeek 0 of 5, and Terra is the default by [Decision 0006](../decisions/0006-terra-is-the-default.md). That doesn't show either is good at the work, and this path hasn't run live on a persistent stack. The check below uses a fake transport.

Set the switch where the worker starts, alongside `AUTOBOTS_CONFIG_ROOT`, `AUTOBOTS_SUPABASE_URL`, `AUTOBOTS_SERVICE_ROLE_KEY` and, if the key file isn't in its default place, `AUTOBOTS_PROVIDER_MASTER_KEY_FILE`, all with the same values the API uses. Missing any of the required ones, the worker refuses to start.

```sh
AUTOBOTS_WORKER_INFERENCE=enabled services/agent/.venv/bin/python -m autobots.operations.worker 2>> "$LOG_DIR/worker.log"
```

Expected: the log's `worker.started` line says `claims_inference` is true, and Operations stops reporting `no_inference_worker`. Any other value of the switch means off. No setting chooses another endpoint or model. The HTTP client does honor the usual proxy variables, so a proxy set for this process carries its traffic.

What each job does:

- **Route:** the `executor` binding in the run's frozen `policy_snapshot` picks the profile, so one worker serves DeepSeek and Terra runs side by side. Changing a workspace default never reaches a run already admitted. A run with no approved binding pauses as `route_not_bound`.
- **Before anything starts:** a job with no usable key or no fresh catalog pauses, with nothing reserved and no request sent. A cancel, or a candidate waiting for verification, still settles, because neither needs a model. A workflow still runs its deterministic blocks, and only its agent blocks stop.
- **Each attempt:** it rechecks the catalog (no older than five minutes), reads the current key, records a stored key's version in `app_private.model_invocations.credential_version` (an environment key has none), and builds a client used once. A rotated key applies from the next attempt, with no restart.
- **Spend:** each call asks for at most 512 output tokens and reserves the most the highest rates that can apply could charge for that plus 32,000 input tokens. That input figure is an estimate, because no tokenizer is pinned, so text with more than a token per character can pass it. The prices are read when the job is claimed, so a rise during a job is under-reserved until its next claim, though a price that disappears stops the next attempt. The reply's reported cost settles the attempt.
- **Compaction:** it works only when a run's `summarizer` binding matches its `executor` binding. Otherwise a run long enough to need it pauses as `route_not_bound`.

| Pause reason | Means | What to do |
|---|---|---|
| `credentials_required` | No effective key | Add a key, then `POST /v1/runs/{run_id}/resume`. Resume answers `409` until then. |
| `invalid_credential` | OpenRouter answered `401`, or the configured key is unusable. Sent once, not retried, and the key is marked invalid | Replace or revalidate the key, then resume. Resume answers `409 credential_invalid` until then. |
| `credential_unavailable` | The master key, the credential row or the configuration root can't be read, or the last key check couldn't reach OpenRouter | Restore access, revalidate the key, or replace it if its row is damaged. Never generate a new master key while encrypted rows exist. |
| `model_unavailable` | The catalog is stale or unreadable, the mapping drifted, the model no longer offers tools or the output limit, or OpenRouter answered `404` | Read the catalog. Nothing substitutes another model. Resume once it's right, or start a new run on another model. |
| `cost_unavailable` | The catalog gives no usable price | Same as above. |
| `network_before_acceptance` | Two retries also couldn't open a connection, so nothing was sent | Check this Mac's network, then resume. |
| `uncertain_acceptance` | A call timed out or dropped, or OpenRouter answered in a way the SDK couldn't parse. It may have been charged, so its reservation stays | Look up the charge in OpenRouter's records, reconcile it as in [Drain and stop](#drain-and-stop), then resume. Resume answers `409 uncertain_model_call` until then. |

These don't pause: after two retries, `rate_limited` (`429`) and `provider_error` (other `5xx`) fail the run. A `Retry-After` is honored up to 60 seconds, and one longer than that, or past the run's time limit, ends the retries at once. Neither `402` nor a `401` is retried. To continue failed work, start a linked new run. A reply that the provider itself stopped, as `error` or `content_filter`, never runs and fails as `incomplete_output`.

**Qualified by** `python3.12 scripts/qualify_worker_inference.py`, on its own disposable stack. It runs the real `worker.main`, SDK and adapter, with a fake HTTP transport and catalog passed from Python, arranged keys, and hostnames beyond loopback refused. It writes `.checks/worker-inference/qualification.json` and its logs under `.checks/worker-inference/logs`, and removes only its own `autobots-disposable-*` project. Other Docker stacks must stay still while it runs, because it compares every container outside its own project.

It makes no paid call, and says nothing about a live route, real response shapes, real prices or real billing. Its fake replies don't exercise compaction, a workflow or child run through this worker, two workers at once, a lost lease, or Terra's mandatory reasoning within 512 output tokens, which belongs to US-3.4.

## The GitHub issue connector

The first consequential connector, by [Decision 0007](../decisions/0007-first-connector-github-issues.md). It creates an issue in one repository and does nothing else. An owner grants it per Expert, goals without an Expert don't get it, and each call waits for a person's approval.

Set both for the worker:

```sh
AUTOBOTS_GITHUB_ISSUES_REPOSITORY=owner/name
AUTOBOTS_GITHUB_ISSUES_TOKEN=<a fine-grained token limited to that repository, with Issues read and write>
```

The token is read for each attempt and stored nowhere. Without both, a call fails as `connector_not_configured` and sends nothing.

- **Refused by GitHub:** the call fails as `github_refused_<status>`, with that code on the receipt, and created nothing.
- **Uncertain:** a lost reply or an unclear status records `unknown`. The connector looks for its marker in the newest 100 issues and only sends again if it isn't there, so an issue that hasn't appeared yet, or a repository busier than that, could be duplicated.

Qualify it against a throwaway private repository. The script refuses a broad token or a public repository, writes one issue and closes it:

```sh
PYTHONPATH=services/agent/src services/agent/.venv/bin/python scripts/qualify_github_connector.py --live --repository owner/throwaway --token-file /path/outside/this/repository
```

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
| Checkpoints | `adapter_unqualified` | refused, and nothing is claimed | This release's checkpoint adapter has no recorded qualification. See [the upgrade runbook](upgrade.md). |

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

`receipt_days` needs `run_days` and can't be shorter than it. A key stays while its run is inside the window, or has an unresolved effect or call. A run is refused, and retried on the next pass, while its tree is active, a continuation of it is active, or it has a `started` or `unknown` tool receipt. Purges are recorded in `app_private.retention_log`. If Storage is down, rows commit and bytes wait for the next pass.

A purged run has no explanation on its page yet: its artifacts just aren't listed.

## Backup and restore

See [the backup and restore runbook](backup-restore.md).

## Failure symptoms

- **`503 not_ready` with everything apparently up:** read the conditions. A disk below the minimum refuses admission on its own.
- **Queued forever:** expected unless a worker is running with `AUTOBOTS_WORKER_INFERENCE=enabled`. See [Turning on inference](#turning-on-inference).
- **A run paused after a restart:** read its reason. An uncertain call or unknown effect is waiting for a person, not stuck.

## Cleanup

Nothing here creates anything to clean up. `scripts/qualify_operations.py` removes only its own `autobots-disposable-*` project, and its logs go to the ignored `.checks/operations/logs`.
