# Runbook: local operations

Starting, draining, stopping and reading the health of the local stack, and applying retention.

**Last exercised:** on the real install on 2026-11-06, [as US-11.3 records](../../../openspec/changes/archive/2026-11-06-us-11-3-guarded-persistent-install-exercised/verification.md), with a real goal, a drain, a stop and a start. Its project is `autobots-install`, on `127.0.0.1:55321` and `127.0.0.1:55322`, because `54321` and `54322` belong to another project, with its files in `~/.local/share/autobots-install`. `python3.12 scripts/qualify_operations.py` still runs this procedure on a disposable project with a scripted model, including what the real install didn't: a run cut short by a drain, and retention. Real sleep is exercised on a disposable stack, by [its own runbook](mac-sleep.md).

## Prerequisites and target

- `PROJECT` is the Compose project you mean to touch. Check it first. Never run these against another project on this Mac.
- Docker with the pinned images, the prepared `services/agent/.venv`, and an env file holding the values in [the local app runbook](local-app.md). No secret goes on a command line or into a log.
- Named volumes hold the data. Nothing here removes them. `docker compose down -v`, `docker volume rm`, `docker system prune` and a database reset are not part of any routine step.

## Start

In this order, as LM-07 states.

```sh
docker compose -p "$PROJECT" --env-file "$ENV_FILE" -f infra/supabase/upstream/docker-compose.yml -f infra/supabase/compose.overlay.yaml up -d --wait --wait-timeout 240
```

Then apply reviewed migrations with [the guarded apply](local-supabase.md#the-persistent-install). It's refused unless the project is the recorded install. Then start the processes, with `set -a; . "$APP_ENV"; set +a` first, where `APP_ENV` is the install's `app.env`:

```sh
services/agent/.venv/bin/python -m uvicorn --factory autobots.api.main:create_configured_app --host 127.0.0.1 --port 8001 --no-access-log 2>> "$LOG_DIR/api.log"
services/agent/.venv/bin/python -m autobots.operations.worker 2>> "$LOG_DIR/worker.log"
```

Expected: `GET /v1/operations/local-status`, or the Operations page, says ready. Until then, `POST /v1/runs` and starting a workflow answer `503 not_ready`, and nothing is queued.

## What the worker does today

`autobots.operations.worker` expires approvals, evaluates routines and applies retention. **By default it doesn't claim jobs**, because claiming spends real money. Queued runs wait. With at least one queued, Operations says `no_inference_worker`, and with none it says `worker_ready`, as observed on the install.

## Turning on inference

**This spends real money once a key exists: every queued run in every workspace with a key sends billed requests to OpenRouter.** Both routes have met the real provider ([with their limits](../evidence/US-3.4/summary.md)). [One goal, repeated on disposable stacks,](../evidence/LIVE-GOAL-1/summary.md) went Terra 5 of 5 and DeepSeek 0 of 5, and Terra is the default by [Decision 0006](../decisions/0006-terra-is-the-default.md). That doesn't show either is good at the work. [One goal has run on the real install](../../../openspec/changes/archive/2026-11-06-us-11-3-guarded-persistent-install-exercised/verification.md), on Terra. The check below uses a fake transport.

Set the switch where the worker starts, alongside `AUTOBOTS_CONFIG_ROOT`, `AUTOBOTS_SUPABASE_URL`, `AUTOBOTS_SERVICE_ROLE_KEY` and, if the key file isn't in its default place, `AUTOBOTS_PROVIDER_MASTER_KEY_FILE`, all with the same values the API uses. Missing any of the required ones, the worker refuses to start.

```sh
AUTOBOTS_WORKER_INFERENCE=enabled services/agent/.venv/bin/python -m autobots.operations.worker 2>> "$LOG_DIR/worker.log"
```

Expected: the log's `worker.started` line says `claims_inference` is true, and Operations stops reporting `no_inference_worker`. Any other value of the switch means off. No setting chooses another endpoint or model. The HTTP client does honor the usual proxy variables, so a proxy set for this process carries its traffic.

What each job does:

- **Route:** the `executor` binding in the run's frozen `policy_snapshot` picks the profile, so one worker serves DeepSeek and Terra runs side by side. Changing a workspace default never reaches a run already admitted. A run with no approved binding pauses as `route_not_bound`.
- **Before anything starts:** a job with no usable key or no fresh catalog pauses, with nothing reserved and no request sent. A cancel, or a candidate waiting for verification, still settles, because neither needs a model. A workflow still runs its deterministic blocks, and only its agent blocks stop.
- **Each attempt:** it rechecks the catalog (no older than five minutes), reads the current key, records a stored key's version in `app_private.model_invocations.credential_version` (an environment key has none), and builds a client used once. A rotated key applies from the next attempt, with no restart.
- **Spend:** each call asks for at most 512 output tokens and reserves the most the highest rates that can apply could charge for that plus 32,000 input tokens. A request larger than that reserves for its bytes as well. That input figure is an estimate, because no tokenizer is pinned, so text with more than a token per character can pass it. The prices are read when the job is claimed, so a rise during a job is under-reserved until its next claim, though a price that disappears stops the next attempt. The reply's reported cost settles the attempt.
- **Compaction:** it works only when a run's `summarizer` binding matches its `executor` binding. Otherwise a run long enough to need it pauses as `route_not_bound`.

| Pause reason | Means | What to do |
|---|---|---|
| `credentials_required` | No effective key | Add a key, then `POST /v1/runs/{run_id}/resume`. Resume answers `409` until then. |
| `invalid_credential` | OpenRouter answered `401`, or the configured key is unusable. Sent once, not retried, and the key is marked invalid | Replace or revalidate the key, then resume. Resume answers `409 credential_invalid` until then. |
| `credential_unavailable` | The master key, the credential row or the configuration root can't be read, or the last key check couldn't reach OpenRouter | Restore access, revalidate the key, or replace it if its row is damaged. Never generate a new master key while encrypted rows exist. |
| `model_unavailable` | The catalog is stale or unreadable, the mapping drifted, the model no longer offers tools or the output limit, or OpenRouter answered `404` | Read the catalog. Nothing substitutes another model. Resume once it's right, or start a new run on another model. |
| `cost_unavailable` | The catalog gives no usable price, a fresh price is above what was reserved, or the request could reach a higher long-prompt rate that nothing was reserved at, such as Terra's from 272,000 tokens. That's counted in bytes at one token each, so it can refuse before the rate would apply | For the first two, the same as above. For the last, resuming only pauses again, because the context doesn't shrink: cancel the run and use **Continue in a new run**. A child or a workflow's run has no such button, so it can only be cancelled |
| `network_before_acceptance` | Two retries also couldn't open a connection, so nothing was sent | Check this Mac's network, then resume. |
| `uncertain_acceptance` | A call timed out or dropped, or OpenRouter answered in a way the SDK couldn't parse. It may have been charged, so its reservation stays | `$LOG_DIR/worker.log` has a `worker.call_uncertain` event saying why: the shortened invocation and run, the exception's type and its cause's, the HTTP status if there was one, or a `reason` of `call_time_limit`. It holds no message or reply text, and it doesn't say what was charged. A cancel that interrupts a call logs the same event with `run_interrupted`, and that run ends cancelled with its outcome unknown. Look up the charge in OpenRouter's records, reconcile it as in [Drain and stop](#drain-and-stop), then resume. Resume answers `409 uncertain_model_call` until then. |

These don't pause: after two retries, `rate_limited` (`429`) and `provider_error` (other `5xx`) fail the run. To go on, a person uses **Continue in a new run** on the failed run, which links a new run that can repeat work with no recorded result. A `Retry-After` is honored up to 60 seconds, and one longer than that, or past the run's time limit, ends the retries at once. Neither `402` nor a `401` is retried. To continue failed work, use **Continue in a new run** on its page. Its steps are new, so it can repeat what the earlier run did, and anything consequential waits for a new approval. A reply that the provider itself stopped, as `error` or `content_filter`, never runs and fails as `incomplete_output`.

**Qualified by** `python3.12 scripts/qualify_worker_inference.py`, on its own disposable stack. It runs the real `worker.main`, SDK and adapter, with a fake HTTP transport and catalog passed from Python, arranged keys, and hostnames beyond loopback refused. It writes `.checks/worker-inference/qualification.json` and its logs under `.checks/worker-inference/logs`, and removes only its own `autobots-disposable-*` project. Other Docker stacks must stay still while it runs, because it compares every container outside its own project.

It makes no paid call, and says nothing about a live route, real response shapes, real prices or real billing. Its fake replies don't exercise compaction, a workflow or child run through this worker, two workers at once, a lost lease, or Terra's mandatory reasoning within 512 output tokens, which belongs to US-3.4.

## Reasoning metadata across a tool call

A route can return opaque reasoning metadata with a tool call, and LC-23 wants it sent back unchanged. `autobots.operations.reasoning_trial` compares the HTTP bodies of a real reply and its continuation, and keeps only where they differ, never the metadata. Nothing is sent without `--paid`. It counts against the ledger in `.checks/decision-0009/ledger.json`, shared with the persistent install's goals, and refuses to start a route's trial when its worst case would take that ledger past US$1.

```sh
PYTHONPATH=services/agent/src services/agent/.venv/bin/python -m autobots.operations.reasoning_trial --paid --key-file .env
```

`survived` means unchanged in content and order. `lost` names what differed. `not_exercised` means the route returned nothing to preserve, or made no tool call. `not_run` means the cap stopped it. [The last result](../../../openspec/changes/archive/2026-11-06-us-11-2-reasoning-continuation-check/verification.md) is that Terra's encrypted item comes back with its `id` removed, by the pinned SDK, so LC-23 is partial on that route.

## Tool-provider keys

Tool providers are data services the worker calls as tools, not inference providers ([Decision 0017](../decisions/0017-tool-catalog.md#decision)). Each key is optional, read by the worker for each attempt from its environment, and stored nowhere. A missing key makes only that provider's tools unavailable: the Tools page says so with the variable to set, and a run or Expert version that grants one of them is refused `tool_unavailable` or `expert_tool_unavailable` before anything starts. Other runs are unaffected.

```sh
TAVILY_API_KEY=<for tavily_search, tavily_extract, tavily_map and tavily_crawl>
JINA_API_KEY=<for search_web and extract_website_content>
```

Set them for both the worker and the API, since the API reports availability from its own environment, then restart both. On the persistent install, `make start` passes `TAVILY_API_KEY` and `JINA_API_KEY` from the repository's `.env` to both. It parses the file as data, never sources it, and takes nothing else from it.

By [Decision 0024](../decisions/0024-tool-keys-from-env-and-settings.md), the Tavily and Jina keys can also be saved per workspace at Settings → Keys & vars (Settings → Tool keys until [Decision 0025](../decisions/0025-keys-and-vars.md)). The order, highest first:
1. The workspace's key saved in Settings, sealed with the master key like the OpenRouter key.
2. The process environment.
3. The `.env` files under `AUTOBOTS_CONFIG_ROOT`, in MP-03's order.

The first non-blank value wins, and each call resolves its key, so a saved key applies from the next call with no restart. Only the owner can save or remove a key. Saving checks its shape only and calls no provider. Removing it falls back to the environment, and nothing edits `.env`. Saving needs migration 51 (`20261108000051_tool_provider_keys.sql`). On an install that predates it, run `make migrate`, then `make stop && make start`.

Nothing checks a key against its provider automatically, because that costs a request: tests use fake transports even with a key present, and a live check is a separate task an owner authorizes and caps. A root run tree may make 20 metered tool calls; the next is denied `tool_budget_exceeded` before any request.

## The browser executor

The isolated browser executor ([Decision 0018](../decisions/0018-browser-executor.md), US-14.13) runs one disposable Chromium container per browsing call, behind an egress sidecar that is its only way out and the only door to its DevTools. `browse_goal` uses it, and stays disabled until the executor is qualified at the current code and turned on (below).

Build both images on this Mac, through the one build entry point. The browser image starts from the Playwright 1.64.1 image pinned by digest, and the proxy from the Python 3.12.16 image (`python:3.12.16-slim-bookworm`) pinned by digest, so a build pulls a base only if it is absent:

```sh
make browser-images
```

It runs `scripts/browser_images.py build`. Each Dockerfile's own `<Dockerfile>.dockerignore` narrows its build context to the one file it copies, and each image gets the label `autobots.fingerprint`: a digest of the executor's fingerprint, which hashes the two Dockerfiles and their ignore files, the entrypoint, `egress_proxy.py` and the executor's three modules, `browser_executor.py` (the Docker session), `browser_cdp.py` (the DevTools client and request guard) and `browser_qualification.py` (what a qualification binds), plus `application/browser_leases.py` (the sweeper's lease and attempt checks). To see whether the local images carry the current fingerprint, without changing anything:

```sh
python3.12 scripts/browser_images.py check
```

It exits 0 when both are current, 1 when either is missing or was built from other sources, and 2 without Docker.

Then qualify it. This starts a disposable database, drives the browser with a scripted driver, never a model, and needs outbound network to `https://example.com/` (and `example.org` for the request cap), the only hosts it reaches. It refuses, before starting anything, images whose label isn't the current fingerprint's:

```sh
python3.12 scripts/qualify_browser_executor.py
```

It writes `.checks/browser-executor/qualification.json`, bound to the fingerprint it started with. The executor reports qualified only from a passing report at the current fingerprint, and only while both images it starts carry that fingerprint's label, so after changing any file the fingerprint names, run both commands again. Until then `browse_goal` is off. It's in no verification profile, since it needs network and images a check never builds.

**Re-qualification owed.** The executor's split into three modules, the image labels and the sweeper's lease and attempt queries, now in the fingerprinted `application/browser_leases.py`, changed the fingerprint, so the qualification recorded on 2026-11-07 reads as stale and `browse_goal` is off, the safe state. Re-qualifying is the owner's step ([Decision 0029](../decisions/0029-refactor-decisions-delegated-r41-r68.md) F4, [Decision 0018](../decisions/0018-browser-executor.md) B8). It needs Docker, the base images (pulled once if absent) and outbound network to the qualification host:

```sh
make browser-images && python3.12 scripts/qualify_browser_executor.py
```

What a session is: a non-root container from the pinned image with all capabilities dropped, `no-new-privileges`, a read-only root, a 256 MiB `/tmp`, 1 CPU, 1 GiB, 256 processes and 300 seconds, on an internal network. The sidecar allows only `CONNECT` to port 443 of the hosts the call names, refuses any address that isn't public and connects to the one it checked, and caps requests and bytes. DevTools are published on `127.0.0.1` only, on a random port, behind a per-session token. Losing the lease, cancelling the run or reaching a cap removes the session; a sweeper removes containers labelled `autobots.browser` that a crashed worker left:

```sh
docker ps -a --filter label=autobots.browser=1
```

### Turning on `browse_goal`

`browse_goal` (US-14.12, [Decision 0020](../decisions/0020-own-browsing-loop.md)) is Autobots' own read-only browsing loop on that executor. It's off until both are true: the executor is qualified as above, and the owner turns it on for the API and the worker:

```sh
AUTOBOTS_BROWSER_EXECUTOR=enabled
```

Then restart both. A workspace can also save `enabled` or `disabled` at Settings → Keys & vars, which wins over the environment for that workspace ([Decision 0025](../decisions/0025-keys-and-vars.md) V4). On the persistent install, set it in the repository's `.env`: `make start` passes it to the API and the worker when it is exactly `enabled` ([Decision 0024](../decisions/0024-tool-keys-from-env-and-settings.md) K7), then `make stop && make start`. The Tools screen lists it as available, and an Expert can grant it. Plain goals and workflows can't, and a run with no Expert behind it is refused `expert_grant_required`. Every call waits for a person's approval, which shows its task, start URL, domains and limits, before any container starts. Each step is a paid model call on the run's `researcher` route, admitted against the run's budget, and the call counts as one metered tool call. Unset the variable, or let the qualification go stale, and it is disabled again at the next call.

To check it end to end without a model, on a disposable database, against `https://example.com/`:

```sh
python3.12 scripts/qualify_browse_goal.py
```

It writes `.checks/browse-goal/check.json`. It's in no verification profile, for the same reason as the executor's.

The one live trial with a real model (US-14.16, [Decision 0019](../decisions/0019-sol-profile-and-browser-use.md) S6) ran on 2026-11-07. It browsed from `https://example.com/` within `example.com` and `iana.org` on Sol, under a US$1 run budget. The trial's own process read only `OPENROUTER_API_KEY` from the key file:

```sh
python3.12 scripts/browse_trial.py --key-file .env
```

Its record is `.checks/browse-trial/result.json`. Started again, it refuses before anything starts. A repeat needs the owner's request, given as `--owner-requested-repeat`.

## The GitHub tools

The repository and token resolve per workspace by [Decision 0025](../decisions/0025-keys-and-vars.md):
1. The values saved at Settings → Keys & vars (the token sealed, the repository as `owner/name`).
2. The process environment, where `make start` passes them from `.env`.
3. The configuration root's `.env` files.

An approved write keeps the repository its approval recorded. If the setting changes before it runs, it is refused `approval_target_changed` and nothing is written. Saving them needs migration 52.

All on one configured repository, by [Decision 0007](../decisions/0007-first-connector-github-issues.md), widened by [Decision 0022](../decisions/0022-studio-product-surfaces.md#decision) D6. An owner grants them per Expert, and goals without an Expert don't get them. No tool takes a repository from the model.

- **`create_github_issue`** creates an issue, and each call waits for a person's approval.
  - Version 2 adds up to 10 labels. New grants get version 2.
  - A run whose grants pinned version 1 keeps calling version 1, which is unchanged.
- **Four read-only tools** need no approval and leave no receipt:
  - `github_list_pull_requests`
  - `github_list_workflow_runs`
  - `github_search_issues`, pinned to the repository
  - `github_read_file`, text up to 1 MiB, whose content never appears on run screens.

Set both for the worker and the API, then restart both:

```sh
GITHUB_REPOSITORY=owner/name
GITHUB_TOKEN=<a fine-grained token limited to that repository>
```

The token's repository permissions are exactly:
- Issues: read and write
- Pull requests: read and write
- Contents: read and write
- Actions: read
- Metadata: read

Until both are set, Tools shows every GitHub tool as `key_missing`, with this repair.

The token is read for each attempt and stored nowhere. Without both, a call fails as `connector_not_configured` and sends nothing.

**Use a token made for this, not your own.** `GITHUB_TOKEN` is also the name GitHub's own tools and CI read, so a broader developer token exported under that name in the worker's shell would be picked up by the connector without anyone choosing it ([Decision 0017](../decisions/0017-tool-catalog.md#conflicts-with-existing-rules), C8). Start the worker from a shell where the variable holds only the fine-grained token above.

- **Refused by GitHub:** the call fails as `github_refused_<status>`, with that code on the receipt, and created nothing.
- **Uncertain:** a lost reply or an unclear status records `unknown`. The connector looks for its marker in the newest 100 issues, for about 15 seconds because GitHub's list can lag a new issue, and only sends again if it never appears. An issue slower than that, or a repository busier than that, could be duplicated.

Qualify it against a throwaway private repository. The script refuses a broad token or a public repository, writes one issue and closes it:

```sh
PYTHONPATH=services/agent/src services/agent/.venv/bin/python scripts/qualify_github_connector.py --live --repository owner/throwaway --token-file /path/outside/this/repository
```

## The cronjob tool

`cronjob` ([Decision 0026](../decisions/0026-cronjob-tool-and-tool-guide.md), US-14.19) lets an Expert manage this workspace's routines.
- **Actions:** list, create, update, pause, resume, run now and remove. They go through the same service as the Routines API.
- **Approval:** `list` runs without approval. Every other action waits in Approvals, showing the action, the routine and its schedule, because a routine can start paid runs.
- **Who can use it:** only an Expert can grant it.
- **Run now:** it follows the scheduled path. An active run skips it (`skipped_overlap`), and a workspace with no usable key blocks it. A paused routine is refused with `routine_paused`.
- **Remove:** a removed routine is hidden and never evaluated again. Its versions, occurrences and runs stay, and its name can be reused.
- **Migration:** removal needs migration 53. Run `make migrate`, then `make stop && make start`.

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

The page also shows delayed routine occurrences, OpenRouter's availability from its public catalog, which is no model call, restore history and each route's qualification date and limits.

With the database down the page still answers, with `scope: installation` and no workspace counts. Only an owner sees it while the database is up.

Logs are JSON lines on stderr, kept in `$LOG_DIR` on this Mac. Secret shapes are replaced with `[redacted]` and identifiers are cut to eight characters. An exception logs its type, never its message, and uvicorn's own lines go through the same format, apart from access lines, which aren't logged. API and worker bootstrap turn inherited LangSmith and OTLP settings off, and Operations reports it.

## Drain and stop

In this order: web and API first so nothing new is admitted, then the worker, then containers.

```sh
kill -TERM "$WEB_PID"
kill -TERM "$API_PID"
kill -TERM "$WORKER_PID"
docker compose -p "$PROJECT" stop
```

Expected: the worker logs `worker.stopped`, and its heartbeat ends at `stopped`. With a step still running it first goes to `draining` and logs `worker.draining`. On the install no step was running, so only `worker.stopped` appeared. A step finishes if it can within `AUTOBOTS_WORKER_DRAIN_SECONDS` (default 30). uvicorn exits with status -15 after `Application shutdown complete`, which is its normal clean stop.

A step that's still running can send further paid calls during the drain, as a stop only prevents new claims.

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

## Mac sleep

A worker that wakes takes back a lease that ran out with nobody claiming it, and doesn't count the time asleep as active. A call whose connection dropped should pause the run as `uncertain_acceptance`, as above, though that path hasn't been exercised under a real sleep. See [the sleep runbook](mac-sleep.md), which is the only way to exercise this: `SIGSTOP` doesn't separate the two clocks, so it never counts as a sleep.

## Failure symptoms

- **`503 not_ready` with everything apparently up:** read the conditions. A disk below the minimum refuses admission on its own.
- **Queued forever:** expected unless a worker is running with `AUTOBOTS_WORKER_INFERENCE=enabled`. See [Turning on inference](#turning-on-inference).
- **A run paused after a restart:** read its reason. An uncertain call or unknown effect is waiting for a person, not stuck.

## Cleanup

Nothing here creates anything to clean up. `scripts/qualify_operations.py` removes only its own `autobots-disposable-*` project, and its logs go to the ignored `.checks/operations/logs`.
