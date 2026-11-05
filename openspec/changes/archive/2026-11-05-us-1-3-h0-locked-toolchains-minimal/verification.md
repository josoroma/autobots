# Verification — us-1-3-h0-locked-toolchains-minimal

Change: us-1-3-h0-locked-toolchains-minimal
OpenSpec verify: VERIFIED by the main session, with the limits below. No independent review, per Decision 0003.
Verified: 2026-11-05

Base revision `d45fd7d`, working tree with this change. CLI, Python and Node runs were real and local. No application model call, service or database.

## Scenarios

**Resolve the combined environment: observed.**
- `scripts/toolchain.py lock`, `bootstrap` and `check` exit 0 on the real tree; all 13 check steps pass, including ruff, mypy, pytest, lint, typecheck and `next build`.
- Lock hashes are identical before and after: `pnpm-lock.yaml` `d463a2c5…`, `services/agent/uv.lock` `1fbaf587…`.
- Recorded versions: Node 22.23.2, pnpm 12.16.1 through Corepack 0.34.6, Python 3.12.16, uv 0.13.6; `deepagents` 0.7.32, `langchain` 1.4.8, `langgraph` 1.2.19, `langchain-openrouter` 0.2.9, `fastapi` 0.162.0, `psycopg` 3.3.8, `next` 16.4.5, `react` 19.3.1, `typescript` 6.0.3, `eslint` 9.39.5.
- `tests/toolchain` ran 47 tests, including fresh-cache reproducibility and scaffold scope, exit 0.

**Keep verification non-mutating: observed.**
- `check`'s guard reports no differences. `tests/toolchain/test_non_mutating.py` negative cases N1 to N7 pass on disposable copies: stale locks and drifted environments fail, and nothing is installed or rewritten.
- `git status` lists no generated output after `check`.

## User decisions applied

- Anthropic and Google SDKs (`anthropic` 2.5.0, `langchain-anthropic` 1.7.10, `google-genai` 2.34.0, `langchain-google-genai` 4.4.3) are locked as unused transitive dependencies of `deepagents`. No import of them exists in `services/agent/src` or `services/agent/tests`. DH-01 says this milestone adds no Anthropic SDK; the user resolved that conflict.
- Node pinned to 22.23.2. pnpm repo-local through Corepack, no `corepack enable`. Global `pnpm` is still absent.

## Findings

- **Deviations from the plan's design:** `stateDir` was replaced by `XDG_*` variables under `.cache/xdg`, because pnpm ignores it there, so user-level tool configuration is not read; `COREPACK_ENABLE_DOWNLOAD_PROMPT=0` added; `cache-keys` added to `[tool.uv]`, so rewriting `pyproject.toml` needs a re-bootstrap; `apps/web/tsconfig.json` holds the values `next typegen` writes; `create_app()` disables OpenAPI and docs routes, which US-2.2 may revisit.
- **Pins with no source:** development tools (`ruff`, `mypy`, `pytest`, `prettier`, `@types/*`) and `pnpm` are registry observations. `typescript` and `eslint` sit below latest because of peer ranges.
- **Build scripts were not audited:** `pnpm ignored-builds` was inconclusive; only `sharp` and `unrs-resolver` were checked.
- **Machine state:** the listed paths and `command -v pnpm` are unchanged, which does not rule out writes elsewhere.
- **Runbook:** Commands were run as written, except the delete in "Cleanup and rollback" and the recovery rows, which are untested. Last exercised on 2026-11-05 at this base revision, with the results above.
- **Plan text:** `implementation-plan.md`, `design.md` and `tasks.md` name the removed manifest, review, test and coordinator steps. They predate Decision 0003; `design.md` line 133's `story_manifest.py` no longer exists.
- This is not H0, H1 or product acceptance, and the scaffold has no feature behavior.
