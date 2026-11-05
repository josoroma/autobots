## Why

The product needs native local API and presentation processes with clear ownership, and SP-004, SP-014, LC-34 and DS-01–05 require a guarded same-origin boundary and the exact Luma interface, dark by default.

## What Changes

- FastAPI factory with lifespan-owned pool, settings read at the entry point, internal credential, session verification, membership check and safe errors. First routes: `GET /v1/health` and `GET /v1/workspaces/{id}`, with generated client operations.
- Next.js shell: `shadcn`-style components on the exact tokens, imported unedited from `docs/design/luma.css`. Dark default through `next-themes`, with an appearance control and a same-origin BFF that checks `Host`, `Origin` and CSRF and adds the internal credential on the server.
- `scripts/qualify_web.py` runs real local processes and a real browser, and `full` includes it. Evidence goes under `docs/engineering/evidence/US-2.5/`, as DS-05 and this story's acceptance ask.
- Pinned, repo-local dependencies: `next-themes`, `tailwindcss`, `@tailwindcss/postcss`, `clsx`, `tailwind-merge`, `class-variance-authority`, `lucide-react`, `@playwright/test`, `@axe-core/playwright`, plus direct pins for `uvicorn`, `pyjwt` and `psycopg-pool`, already locked transitively. A Chromium build for Playwright, under the ignored `.cache/`.

**Limits, by story order:** real Auth sessions and membership are US-2.3, so the default store denies every workspace and qualification arranges a membership. Run admission is a later story, so the "requests do not own work" check is static.

## Capabilities

### New Capabilities

- `local-application-shell`: native services, a guarded same-origin boundary and the shared Luma interface.

### Modified Capabilities

None.

## Impact

`apps/web`, `services/agent/src/autobots/api`, contracts and generated client, both locks, `scripts/verify.py`, `scripts/harness_lib.py`, `tests/toolchain/test_manifests.py`, runbooks and `CODEBASE.md`. No database, service stack or model call.
