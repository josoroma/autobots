# Runbook: local web and API processes

## Scope and prerequisites

Native Next.js on `127.0.0.1:3000` and the Python API on `127.0.0.1:8001`, with the prepared environments from [the toolchains runbook](toolchains.md). No model is called. Real Auth and workspace membership arrive with US-2.3, so until then the API's default store denies every workspace.

The browser suite needs the pinned Chromium for the locked `@playwright/test`, repo-local and Git-ignored, installed once and on purpose:

```sh
PLAYWRIGHT_BROWSERS_PATH="$PWD/.cache/ms-playwright" PATH="$HOME/.nvm/versions/node/v22.23.2/bin:$PATH" apps/web/node_modules/.bin/playwright install chromium
```

## Start the processes

Both need the same internal token, generated once and never committed. The API also needs the Auth JWT secret.

```sh
export AUTOBOTS_INTERNAL_TOKEN="$(python3.12 -c 'import secrets; print(secrets.token_hex(32))')"
AUTOBOTS_JWT_SECRET=<auth jwt secret> PYTHONPATH=services/agent/src services/agent/.venv/bin/uvicorn --factory autobots.api.main:create_configured_app --host 127.0.0.1 --port 8001
apps/web/node_modules/.bin/next start apps/web -H 127.0.0.1 -p 3000
```

Expected: `http://127.0.0.1:3000` shows the workbench, dark on a first visit, with `Python API: available`. Without the API it shows `Python API: unavailable`. Settings → Appearance switches Dark and Light, and issues no request. `AUTOBOTS_API_URL` and `AUTOBOTS_ALLOWED_ORIGIN` change the defaults.

## Boundaries

The browser calls only `/api/v1/...` on the same origin. That route refuses a wrong `Host` or `Origin` and, on writes, a missing or mismatched CSRF token, then adds the internal credential on the server. The API requires that credential on every route, verifies the session token and checks membership. Browser-supplied user and workspace IDs are not trusted, and errors carry only a code and a short message.

## Qualify

```sh
python3.12 scripts/qualify_web.py
jq -r '.status, .stats, (.cases[] | select(.status != "passed") | .id)' .checks/web/qualification.json
```

Expected: exit 0. It builds, starts the real API with an arranged membership and two web servers, one with its API unreachable, on free loopback ports with generated values, drives Chromium, and stops them. `full` runs this. `--retain docs/engineering/evidence/<work item>` also copies the screenshots. Exit 2 means an environment or the browser is missing.

## Failure and recovery

| Symptom | Recovery |
|---|---|
| `Python API: unavailable` | Start the API, and check both processes hold the same internal token |
| `forbidden_host` or `forbidden_origin` | Set `AUTOBOTS_ALLOWED_ORIGIN` to the exact address in the browser |
| Every workspace returns 403 | Expected until US-2.3 connects membership |
| Exit 2 naming the browser | Install it with the command above. No check downloads it |
