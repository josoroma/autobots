## Why

US-15.3, [PRD-Studio SH-04 and HM-05](../../../PRD-Studio.md#shell). Operations' local status is owner-only. A member has no way to see whether the API, worker, database and OpenRouter authentication are ready.

## What Changes

- `GET /v1/readiness`, readable by any member of the workspace. It returns `ready` and four services (`api`, `worker`, `database`, `openrouter`), each `ready`, `not_ready` or `unknown`, with a code. It holds no counts, no paths and no secret. It reads OpenRouter authentication from the stored state only, so it makes no network or model call.
- The shell shows a health line: "All local services ready", or the first service that isn't ready.
- Home shows chips for the API, worker, database and OpenRouter, each in words.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `operations-status`: a member-readable readiness read.

## Impact

- `contracts/operations.py`, `api/operation_routes.py` and `application/provider_settings.py`.
- The generated contract and client.
- `apps/web/components/app-shell.tsx`, a new health component, and `app/page.tsx`.
- Tests: Python API tests and a browser spec.
