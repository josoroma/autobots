# Runbook: local web and API processes

## Scope and prerequisites

Native Next.js on `127.0.0.1:3000` and the Python API on `127.0.0.1:8001`, with the prepared environments from [the toolchains runbook](toolchains.md), and a Supabase stack. No model is called. **Nothing here starts a persistent stack:** only disposable qualification does so far, so the steps below need a stack you already run.

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

## Bootstrap the owner

Public signup is disabled, so the owner is created through the Auth admin API, and a workspace with its owner membership is added through the runtime role. Secrets come from the environment and are never arguments.

```sh
AUTOBOTS_SUPABASE_URL=<gateway url> AUTOBOTS_SERVICE_ROLE_KEY=<service role key> AUTOBOTS_OWNER_PASSWORD=<password> AUTOBOTS_DATABASE_URL=<runtime role url> PYTHONPATH=services/agent/src services/agent/.venv/bin/python -m autobots.operations.bootstrap_owner --email <email> --workspace-name <name>
```

Expected: one line of JSON with the new user and workspace IDs. Exit 1 means a service refused, for example an email already in use. Run it once. `supabase/bootstrap/storage.sql` must already have been applied as the database superuser, because the migration role cannot alter Storage's tables.

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
| Exit 2 naming the browser | Install it with the command above. No check downloads it |
