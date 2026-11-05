# Design

## Context

See `proposal.md` for motivation and observed state. Constraints that shape the approach:

- A new dependency set and two toolchains. OQ-1 to OQ-3 change this design if the user picks another option.
- `/usr/bin/env node` resolves to Node 26 here, and npm, Corepack and package bin shims start through `node` on the search path. A pin in a manifest alone does not select a runtime.
- `harness` must keep working with neither environment present. Its check timeout is 60 seconds and it discovers only `tests/harness`.
- Anything changing the machine beyond this repository needs the user.

## Goals / Non-Goals

**Goals:** one explicit way to lock, prepare and check; verification that cannot install; a failure when it would.

**Non-Goals:** a verification profile, change-impact selection or a report schema. US-1.4 and US-1.5 own those and may absorb `check`.

## Decisions

### D1. Runtimes come from existing installs, selected per process

`.node-version` holds `22.23.2` (OQ-2) and `services/agent/.python-version` holds `3.12.16`. `scripts/toolchain.py` finds an interpreter whose reported version matches the pin, looking on the search path and then under `~/.nvm/versions/node/v<pin>/bin` for Node. It prepends that directory to `PATH` for its child processes only. No match exits 2 and names the tool and wanted version, never the search path.

Python runs through uv with `UV_PYTHON` set to the matching interpreter and `UV_PYTHON_DOWNLOADS=never`. `required-version = "==0.13.6"` selects uv.

*Alternatives:* `.nvmrc` alone does nothing outside an nvm shell. pnpm-managed runtimes would add a new Node runtime, which is OQ-2's third option.

### D2. Pins

Python direct, from PRD section 3.1: `deepagents==0.7.32`, `langchain==1.4.8`, `langgraph==1.2.19`, `langchain-openrouter==0.2.9`, `openrouter==0.11.46`, `langgraph-checkpoint-postgres==3.2.0`, `fastapi==0.162.0`, `psycopg[binary]==3.3.8`, `langchain-mcp-adapters==0.3.2`. `langsmith` stays transitive, as the PRD says. `requires-python = "==3.12.*"`.

Python development, no source names versions, observed resolving with the set above on 2026-11-05: `ruff==0.17.3`, `mypy==2.4.1`, `pytest==9.2.0`, `pytest-asyncio==1.4.1.post1`.

Node, from the shared candidates: `next` 16.4.5, `react` and `react-dom` 19.3.1, all without a range prefix.

Node tools, from DH-06's "compatible pinned" wording and registry peers on 2026-11-05:

| Package | Pin | Why not latest |
|---|---|---|
| `eslint` | 9.39.5 | Latest 10.14.0 is outside the peer ranges of `eslint-plugin-react` 7.37.5, `eslint-plugin-import` 2.32.0 and `eslint-plugin-jsx-a11y` 6.10.2, which `eslint-config-next` 16.4.5 depends on |
| `typescript` | 6.0.3 | Latest 7.0.2 is outside `typescript-eslint` 8.72.1's `>=4.8.4 <6.1.0`. Whether Next.js 16.4.5 accepts 6.0.3 is unobserved. If `next build` or `tsc` rejects it, use 5.9.3 and record why |
| `eslint-config-next` | 16.4.5 | Matches `next` |
| `prettier` | 3.9.10 | Latest |
| `@types/react`, `@types/react-dom` | 19.3.0 | Latest |
| `@types/node` | Latest 22.x at resolve | Matches the Node major, recorded after resolve |
| pnpm | 12.16.1 | Latest, in `packageManager` with its hash (OQ-3) |

A candidate that does not resolve is reported, not replaced. The story's Node set has not been through a resolver.

*`psycopg[binary]`:* the PRD names `psycopg` without extras. Plain `psycopg` needs a system libpq at import, which ties the environment to whatever the machine has. The binary extra keeps the same version. This is a packaging choice the coordinator may overturn.

*`langchain-mcp-adapters`:* section 3.1 calls the listed packages the active selection, so it is locked. Section 3.3 leaves choosing an MCP implementation to later gating, and this story uses neither.

### D3. All tool state stays in ignored repository paths

| State | Location | Rule |
|---|---|---|
| uv cache | `.uv/cache` through `UV_CACHE_DIR` | New: `.uv/` |
| Python environment | `services/agent/.venv` | Exists |
| pnpm itself | `.corepack` through `COREPACK_HOME` | New: `.corepack/` |
| pnpm store | `.pnpm-store` through `storeDir` | Exists |
| pnpm metadata cache and state | `.cache/` through `cacheDir` and `stateDir` | New: `.cache/` |
| Packages | `node_modules` | Exists |
| Next.js output | `apps/web/.next` | Exists |
| Next.js type shim | `apps/web/next-env.d.ts` | New: `next-env.d.ts` |

`.eslintcache`, `.coverage`, `coverage/`, `.hypothesis/` and `.turbo/` get a rule only if a run produces them. This design invokes nothing that should.

### D4. `scripts/toolchain.py` verbs

Standard library only. It imports `reduced_env` from `scripts/harness_lib.py` and `git_paths` and `digest` from `scripts/story_manifest.py`; neither imports it. It accepts `--project-root` so tests can target a disposable copy. Child environments are `reduced_env()` plus `HOME` and the settings below, so no credential is inherited. Exit codes: 0 passed, 1 a check failed, 2 prerequisite unavailable or usage error.

| Verb | Effect | Mutates? |
|---|---|---|
| `versions` | Prints runtime and direct-dependency versions as JSON | No |
| `lock` | `uv lock`; `corepack pnpm install --lockfile-only` | Locks, explicitly |
| `bootstrap` | `uv sync --locked`; `corepack pnpm install --frozen-lockfile` | Ignored environments, explicitly |
| `check` | See D5 | Must not |

### D5. `check` cannot install

Environment: `UV_OFFLINE=1`, `UV_NO_SYNC=1`, `UV_PYTHON_DOWNLOADS=never`, `COREPACK_ENABLE_NETWORK=0`, `COREPACK_ENABLE_AUTO_PIN=0`, `NEXT_TELEMETRY_DISABLED=1`.

Steps, each with a bounded timeout, in order:

1. **Prerequisites:** pinned tools, `services/agent/.venv/bin/python`, `node_modules` and a Corepack entry for the pinned pnpm exist. Otherwise exit 2 before running any tool.
2. **`python_lock`:** `uv lock --check --offline`.
3. **`python_env`:** `uv sync --check --locked --offline`.
4. **Python tools, called directly from `.venv/bin`:** `ruff check`, `ruff format --check`, `mypy`, `pytest`.
5. **`node_lock`:** `corepack pnpm install --frozen-lockfile --lockfile-only --offline`.
6. **Package scripts:** `lint`, `format:check`, `typegen`, `typecheck`, `build`.

**Scratch probe on uv 0.13.6:** `uv lock --check` exited 1 on a stale manifest, online and offline, leaving `uv.lock` unchanged. The offline message mentions disabled network rather than a stale lock, so tests assert the failing step and the unchanged file, not the wording. `uv sync --check` exited 1 with no `.venv` and created none, and exited 1 on a removed package without reinstalling it. `uv sync --locked` created `.venv` even though it failed, which is why it is confined to `bootstrap`.

**Not probed:** pnpm 12. The pnpm documentation pages name `--frozen-lockfile`, `--lockfile-only`, `--offline`, `verifyDepsBeforeRun`, `storeDir`, `cacheDir`, `stateDir` and `engineStrict`, but step 5's combination is unobserved. If it does not fail on a stale manifest, compare the lock's importers with the manifests instead and record the deviation. It may not be replaced by anything that writes.

`pnpm-workspace.yaml` sets `verifyDepsBeforeRun: error`, `engineStrict: true` and `strictPeerDependencies: true`.

No `uv run`, `npx`, `pnpm dlx` or other download-at-runtime launcher, per DH-09.

**Guard.** `check` takes a snapshot before step 2 and after the last step, and exits 1 naming any difference, even if every step passed:

- SHA-256 of both locks and every manifest;
- changed tracked and untracked non-ignored paths with their digests, using `git_paths` and `digest`;
- the names of `*.dist-info` in the environment and of entries in `node_modules/.pnpm`.

Names rather than contents, so bytecode and build output do not trip it. A rewrite of a tracked file shows up as a Git change. It writes its report to the ignored `.checks/toolchain/latest.json`.

### D6. Python package

`services/agent/src/autobots/` contains `__init__.py`, `py.typed` and `api/__init__.py`, plus `api/app.py` with `create_app()` and an empty lifespan. No routes. `build-system` uses `uv_build` pinned to uv's version. The other DH-03 layers (`domain`, `application`, `adapters`, `workers`, `graphs`, `contracts`) wait for the stories that fill them, because nothing in harness qualification needs an empty package.

Ruff targets `py312`, mypy is `strict`, and pytest uses `pytest-asyncio`. Third-party typing exceptions stay narrow and documented.

### D7. Web and contract locations

`apps/web` holds a static App Router layout and page, with no data fetching, client components or design tokens. `tsconfig.json` sets `strict`, `noUncheckedIndexedAccess` and `exactOptionalPropertyTypes`. `next.config.ts` does not set `ignoreBuildErrors`. Lint runs separately from build, and `next typegen` runs before `tsc --noEmit`, per DH-06.

`packages/api-client` and `packages/db-types` each hold a private `package.json` and a README saying the output is generated and which story generates it. `contracts/generated/README.md` does the same. Nothing is generated here.

### D8. Tests stay out of `harness`

Toolchain tests live in `tests/toolchain/`, run by their own command. Package tests live in `services/agent/tests/`. `scripts/verify.py`, `scripts/harness_lib.py` and `tests/harness/` are not edited, so `harness` cannot acquire a dependency on these environments.

These tests need network for their fresh-cache bootstrap. An unreachable registry is a failure, never a skip.

## Risks / Trade-offs

- [`check` overlaps US-1.4's profiles] → It adds no profile, and US-1.4 may absorb or replace it.
- [Lock is stale with respect to the Homebrew Python, which `brew upgrade` can move] → `check` exits 2 naming the wanted version; the runbook covers it.
- [Other platforms are unqualified] → Evidence says this Mac only.
- [pnpm 12 blocks dependency build scripts by default, on my memory of earlier majors] → Observe it; record any allowed or ignored builds.
- [Harness fingerprint omits locks and application paths] → `scripts/story_manifest.py` binds them for this story. US-1.4 owns the wider freshness rule.
