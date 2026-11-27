# Runbook: local web and API processes

The [first slice runbook](first-slice.md) exercises a goal end to end on disposable services.

## Scope and prerequisites

Native Next.js on `127.0.0.1:3000` and the Python API on `127.0.0.1:8001`, with the prepared environments from [the toolchains runbook](toolchains.md), and a Supabase stack. No model is called here. [The persistent install](local-supabase.md#the-persistent-install) is the stack to run these on: its `app.env` holds every value below except `AUTOBOTS_OWNER_PASSWORD`, which is in `owner.env`. These steps ran on it on 2026-11-06, with `set -a; . "$APP_ENV"; set +a` first. `next start` needs a production build from `next build`, and the Node on `PATH` that [the toolchains runbook](toolchains.md) pins.

The browser suite needs the pinned Chromium for the locked `@playwright/test`, repo-local and Git-ignored, installed once and on purpose:

```sh
PLAYWRIGHT_BROWSERS_PATH="$PWD/.cache/ms-playwright" PATH="$HOME/.nvm/versions/node/v22.23.2/bin:$PATH" apps/web/node_modules/.bin/playwright install chromium
```

## Start the processes

Both need the same internal token, generated once and never committed. The API also needs the Auth JWT secret.

```sh
export AUTOBOTS_INTERNAL_TOKEN="$(python3.12 -c 'import secrets; print(secrets.token_hex(32))')"
AUTOBOTS_JWT_SECRET=<auth jwt secret> AUTOBOTS_DATABASE_URL=<runtime role url> PYTHONPATH=services/agent/src services/agent/.venv/bin/uvicorn --factory autobots.api.main:create_configured_app --host 127.0.0.1 --port 8001
AUTOBOTS_SUPABASE_URL=<gateway url> AUTOBOTS_SUPABASE_ANON_KEY=<anon key> apps/web/node_modules/.bin/next start apps/web -H 127.0.0.1 -p 3000
```

Expected: `http://127.0.0.1:3000` shows the workbench, dark on a first visit, with `Python API: available`. Without the API it shows `Python API: unavailable`. Settings → Appearance switches Dark and Light, and issues no request. `AUTOBOTS_API_URL` and `AUTOBOTS_ALLOWED_ORIGIN` change the defaults.

A setting the API or the worker can't start with, such as a malformed `AUTOBOTS_MIN_FREE_BYTES` or `AUTOBOTS_STREAM_SECONDS`, or a worker without `AUTOBOTS_DATABASE_URL`, stops the process at start with `ERROR: <variable> ...` and exit 2. A missing database URL doesn't stop the API, because Local Operations answers without a database. The operator commands use the same codes: 0 done, 1 refused, 2 a setting or argument to fix.

## Bootstrap the owner

Public signup is disabled, so the owner is created through the Auth admin API, and a workspace with its owner membership is added through the runtime role. Secrets come from the environment and are never arguments.

```sh
AUTOBOTS_SUPABASE_URL=<gateway url> AUTOBOTS_SERVICE_ROLE_KEY=<service role key> AUTOBOTS_OWNER_PASSWORD=<password> AUTOBOTS_DATABASE_URL=<runtime role url> PYTHONPATH=services/agent/src services/agent/.venv/bin/python -m autobots.operations.bootstrap_owner --email <email> --workspace-name <name>
```

Expected: one line of JSON with the new user and workspace IDs. Run it once. The files in `supabase/bootstrap/` must already have been applied as the database superuser, `storage.sql` first, because the migration role cannot alter Storage's tables. `persistent_install.py apply` applies them after the migrations and the seed.

It checks the database before it creates anyone: one transaction inserts the workspace and checks that the runtime role can add its owner, then Auth creates the user, then the membership commits with the workspace. That transaction stays open during the one Auth call. Its 20-second timeout applies to each socket operation, not to the whole call, so a slow answer can keep it open longer. That is acceptable for a one-shot command. Nothing it prints holds the password, the service key or the database URL.

| Outcome | Exit | What exists | Recovery |
|---|---|---|---|
| JSON with `user_id` and `workspace_id` | 0 | The owner and the workspace | None |
| `ERROR: set ...` | 2 | Nothing | Set the named variables |
| `REFUSED: ...`, for example the database refused, or Auth refused an email already in use | 1 | Nothing | Fix the cause and run it again |
| `{"status": "workspace_incomplete", "user_id": "<id>"}`, and `INCOMPLETE: ...` on stderr | 1 | The Auth user, with no workspace | Fix the cause it names, then finish it with the command below |
| `UNRESOLVED: ...`, after a server error, a timeout or a reply cut short | 1 | Possibly the Auth user, nothing else | See below |

To finish the workspace for a user that already exists, pass its ID instead of the email. It holds a lock on that ID, reads Auth through the admin API to confirm the user, and refuses a user who already owns a workspace, so running it twice, even at once, can't create a second one. It needs no password. With the install's values loaded as above (`set -a; . "$APP_ENV"; set +a`), so no key is typed:

```sh
PYTHONPATH=services/agent/src services/agent/.venv/bin/python -m autobots.operations.bootstrap_owner --user-id <user id> --workspace-name <name>
```

`UNRESOLVED` means Auth may have created the user: it answered with a server error, or its answer was lost or cut short. Run the original command again. If Auth refuses because the email is already in use, the first attempt did create the user. Find its ID from the same loaded values. curl reads the headers from a here-document, so the key is in neither its arguments nor the shell history, which records only the variable's name:

```sh
curl -sS -H @- "$AUTOBOTS_SUPABASE_URL/auth/v1/admin/users?per_page=1000" <<HEADERS | jq -r --arg email '<email>' '.users[] | select(.email == $email) | .id'
apikey: $AUTOBOTS_SERVICE_ROLE_KEY
Authorization: Bearer $AUTOBOTS_SERVICE_ROLE_KEY
HEADERS
```

Then finish it with `--user-id`.

## Seed the concept Experts and workflows (optional)

This puts the seven concept Experts and seven workflows of PRD-Studio SD-02 into one workspace you name. The Deep research content writer is a draft until a SerpApi key is set. It is not a migration, and it is safe to run again: anything that already has its name in that workspace is kept exactly as it is, so a second run, or your own later edits, are never overwritten. It writes no secret and starts no run.

```sh
AUTOBOTS_DATABASE_URL=<runtime role url> PYTHONPATH=services/agent/src services/agent/.venv/bin/python -m autobots.operations.concept_seed --workspace <workspace id>
```

Run it with the same tool variables the worker has, such as `GITHUB_REPOSITORY` and `GITHUB_TOKEN`, so it sees the same tools as available.
- **An unavailable tool:** an Expert is saved without it, and its purpose says so.
- **Drafts:** Nightly test triage and Release notes from merged PRs are drafts while the GitHub tools are unavailable. Interview synthesis stays a draft until an execution can carry files.

Expected: one line of JSON naming what was created, kept or left as a draft.

## Real examples on the install (paid)

Decision 0023 E6. This spends money, from the shared ledger, so it refuses without `--paid`. It reserves US$0.45 before anything is sent, and refuses while another job is queued or a routine is enabled.

```sh
services/agent/.venv/bin/python scripts/persistent_install.py examples --project autobots-install --paid
```

It signs in as the owner from the install's own record, which it never prints, and does five things:
- runs the concept seed above;
- gives Market watcher and Research analyst `publish_artifact` through one new version each (E7);
- runs two small goals: one on Terra, and one with Brief writer on Sol;
- starts the published Vendor due diligence workflow for one vendor;
- runs one worker with inference on, until the goals end and the workflow waits at its approval or ends.

A goal that already succeeded isn't run again. It writes a private report under the install's `reports/`. A workflow still waiting keeps its whole reservation held in the ledger.

Expected: exit 0. In the app, Approvals shows one `workflow_approval` waiting. To see the screens as the owner without typing the password, run the read-only checks. They write screenshots to `.checks/install-screens`:

```sh
services/agent/.venv/bin/python scripts/persistent_install.py screens --project autobots-install
```

## OpenRouter settings

Settings → Models → OpenRouter shows the source, authentication, catalog and live qualification separately. **Save & validate** sends a transient key to this Mac's server, checks `GET /key` and the public catalog, encrypts it and never starts a run. A rejected key or an outage leaves the previous key in place. Disconnect removes only the workspace's stored key.

The API also needs `AUTOBOTS_CONFIG_ROOT`, the absolute directory holding any `.env` files, which every native process shares. With it unset, settings report unavailable. `AUTOBOTS_PROVIDER_MASTER_KEY_FILE` overrides the default key path. The installation's environment key applies only to a workspace with a row in `app_private.installation_credential_grants`.

Only a user's **Run** reaches the credential gate. Without a key it returns `credentials_required`, and the draft stays in this tab's `sessionStorage`. No credential is stored in the browser. With one, the goal is queued, and only a worker with [the inference switch](operations.md#turning-on-inference) runs it.

## The owner's local model server

A local profile's calls go to `llama-server` on this Mac. Neither the Studio nor a hook starts it or downloads weights, so the owner does both ([Decision 0041](../decisions/0041-local-model-source.md) A4, A5).

Check the release and the weights first. Bonsai 2.5's Q2_0 needs b11556 or later: older builds load it without a warning and produce garbage.

```sh
llama-server --version
python3.12 ~/Models/verify-models.py
```

Expected: `version: 1.1.0 (build 12774, ...)` or later. `verify-models.py` prints a `PASS` line for each pinned model in `~/Models/DOWNLOAD-MANIFEST.json`, including `prism-ml/Ternary-Bonsai-2.5-27B-GGUF` and `unsloth/Inkling-2-Mini-GGUF`. A manifest entry for a model no longer on disk fails its own line only.

Start one model, bound to loopback only. Its `--alias` is the model ID its profile checks before each call:

```sh
llama-server -m ~/Models/Ternary-Bonsai-2.5-27B-GGUF/Ternary-Bonsai-2.5-27B-Q2_0.gguf --alias bonsai-2.5-27b-q2_0 \
  --host 127.0.0.1 --port 9931 -c 65536 -np 1 -fa on -ngl 99 --jinja --reasoning-format deepseek \
  --temp 0.7 --top-p 0.8 --top-k 20 --min-p 0 --presence-penalty 1.5
```

For Inkling 2 Mini, use `-m ~/Models/Inkling-2-Mini-GGUF/Inkling-2-Mini-UD-Q3_K_XL.gguf --alias inkling-2-mini-ud-q3_k_xl --temp 1.0 --min-p 0` with the same other flags. Only one model fits in memory beside the Studio.

```sh
curl -s http://127.0.0.1:9931/v1/models
```

Expected: one model, whose `id` is the alias. The worker reads `AUTOBOTS_LOCAL_MODEL_PORT`, default 9931, and a value that isn't a port stops it at start with exit 2.

**What a run shows:**
- **Nothing listening:** a call on a local profile stops as `local_model_server_unavailable`, and the run waits until the server is started. Nothing is sent, and no other model or source is tried.
- **Another model or alias:** the call stops as `model_unavailable`.
- **Spend:** each local call settles at US$0.

**Qualify it,** on request, with the server running and nothing else using it (US-23.2). This spends nothing and needs no `--paid`:

```sh
services/agent/.venv/bin/python -m autobots.operations.route_qualification --profile local_bonsai_2_5_27b --out .checks/route-qualification
```

Expected: about 39 calls in three trials of US-3.4's twelve fixtures, then measurements at about 8K, 32K and 64K prompt tokens, in roughly half an hour on this Mac. It prints `"spent_usd": "0.00"` and whether the profile is `offerable`. `.checks/route-qualification/report-local_bonsai_2_5_27b.json` keeps every trial, the pins, the server's build and peak footprint, and the sentence a migration records. `--no-measure` skips the measurements, and `--port` names another port. A wrong model or no server refuses with nothing sent.

**Stopping it:** `Ctrl-C` in its terminal. A local profile is offered on the Local source only once its qualification is recorded by migration as `qualified_with_limits`.

## Boundaries

The browser calls only `/api/v1/...` on the same origin. That route refuses a wrong `Host` or `Origin` and, on writes, a missing or mismatched CSRF token, then adds the internal credential on the server. The Supabase session lives in an HttpOnly, same-site cookie, through `@supabase/ssr` on the server only. The API requires the credential on every route, verifies the session token against the Auth JWT secret and checks membership in the database. Browser-supplied user and workspace IDs are not trusted, and errors carry only a code and a short message.

## Qualify

```sh
python3.12 scripts/qualify_web.py
jq -r '.status, .stats, (.cases[] | select(.status != "passed") | .id)' .checks/web/qualification.json
```

Expected: exit 0. It builds, starts the real API with an arranged membership and two web servers, one with its API unreachable, on free loopback ports with generated values, drives Chromium, and stops them. `full` runs this. `--retain docs/engineering/evidence/<work item>` also copies the screenshots. Exit 2 means an environment or the browser is missing.

`python3.12 scripts/qualify_identity.py`, also in `--profile db`, exercises real sign-in, membership, PostgREST and Storage on a new disposable stack, and removes it. Results: `.checks/identity/qualification.json`.

## Failure and recovery

| Symptom | Recovery |
|---|---|
| `Python API: unavailable` | Start the API, and check both processes hold the same internal token |
| `forbidden_host` or `forbidden_origin` | Set `AUTOBOTS_ALLOWED_ORIGIN` to the exact address in the browser |
| Every workspace returns 403 | `AUTOBOTS_DATABASE_URL` is missing or the user has no membership row. No database means no access |
| Owner bootstrap printed `workspace_incomplete` | Finish it with `--user-id`, as in [Bootstrap the owner](#bootstrap-the-owner) |
| Exit 2 naming the browser | Install it with the command above. No check downloads it |
