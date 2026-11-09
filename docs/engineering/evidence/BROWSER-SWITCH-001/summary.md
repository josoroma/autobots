# BROWSER-SWITCH-001: `make start` passes the browsing switch from `.env`

**Date:** 2026-11-08. **Status:** done. **Scope:** a small follow-up to US-14.17 that the owner asked for ("Yes, add it"). It is outside the OhMyOrch delivery loop, so this short record follows DH-W01–06.

## Plan

The owner asked what a successful browsing run needs. The browser images were built, and the executor counted as qualified at the current code, but nothing passed `AUTOBOTS_BROWSER_EXECUTOR` to the install's API and worker. `make start` took only the Tavily and Jina keys from `.env`, and the install's `app.env` doesn't set it.

The fix is to pass that one switch from the repository's `.env` as well, recorded as [Decision 0024 K7](../../decisions/0024-tool-keys-from-env-and-settings.md#decision), with PRD-Tool-Catalog PK-06 amended to match.

## Implementation

- **`scripts/tool_keys_env.py --browser-switch`** prints `export AUTOBOTS_BROWSER_EXECUTOR=enabled` only when the file sets exactly `enabled`, and nothing otherwise. The default mode is unchanged.
- **`Makefile`:** a `BROWSER_SWITCH` line is evaluated beside `TOOL_KEYS`, for the API and worker launches only.
- **Docs:** the operations runbook, README-SETUP-RUN and `.env.example`.

The switch only makes browsing eligible. `executor_ready` still needs a passing qualification at the current code, `browse_goal` stays Expert-only, and every call still waits for approval.

## Review

No independent review ran: the owner asked for the change directly.

## Verification

| Check | Exit | Observed |
|---|---|---|
| `tests/harness/test_tool_keys_env.py` | 0 | 4/4. Both Makefile lines were run in `/bin/sh` against fixture `.env` files in a temporary directory:<ul><li>`enabled` passed.</li><li>`AUTOBOTS_WORKER_INFERENCE=enabled` in the same file didn't.</li><li>`""`, `Enabled`, `true`, `1` and a value with quotes and `; touch` passed nothing and created no file.</li></ul>The earlier key cases still pass |
| `make -n start-worker` | 0 | The launch evaluates both lines before starting the worker |
| `python3.12 scripts/verify.py --profile harness` | 0 | passed |
| `python3.12 scripts/verify.py --profile fast` | 0 | passed |

## Runbook

The owner sets `AUTOBOTS_BROWSER_EXECUTOR=enabled` in the repository's `.env`, applies migration 51 with `make migrate`, then runs `make stop && make start`. The Tools page should then list `browse_goal` as available.

## Limits

- Not exercised on the persistent install. The project's hook keeps the install's environment out of the assistant's commands.
- No run, Expert or workflow has used browsing on the install yet. Such a run makes paid model calls.
- Not H1 or product acceptance.
