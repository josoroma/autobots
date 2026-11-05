# Proposal

Story: US-1.3
Change: us-1-3-h0-locked-toolchains-minimal

## Why

SP-001 item 3, DH-02 H0.3 and SP-020 H0-03 require pinned Node/pnpm and Python 3.12/uv toolchains, manifests, compatible locks and minimal non-feature scaffolding, actually resolved and qualified. None of that exists, and US-1.4's portable profiles depend on it. Today this repository has no manifest, no lock and no scaffold, pnpm is absent, and `/usr/bin/env node` starts Node 26 for anything launched through it.

## What Changes

- Add pinned Python 3.12/uv and Node/pnpm manifests and locks, resolved from the Option B package snapshot, the OpenRouter constraints and DH-06's compatible tools.
- Add `scripts/toolchain.py`, with explicit `versions`, `lock`, `bootstrap` and `check` verbs. It keeps tool state in the repository and sets `PATH` only for the processes it starts. `check` is this story's verification command and is not a `scripts/verify.py` profile.
- Add a minimal FastAPI factory, a static Next.js shell and the generated-contract locations. No routes, features, database, services or model calls.
- Add tests under `tests/toolchain/` and `services/agent/tests/`, including negative tests of verification mutation. None join the `harness` profile.
- Add `docs/engineering/runbooks/toolchains.md` as the DH-W05 procedure.
- Add ignore rules for what these tools generate. `.gitignore` is a protected path, so the coordinator persists the implementer's lines verbatim.

## Non-Goals

- US-1.4: portable `fast` and `full` profiles, change-impact selection and the hook adapter. `scripts/verify.py --profile fast` and `--profile full` still exit 2.
- US-1.5: work-record and evidence templates, and the DH-09.2 manifest schema.
- US-1.6: deliberate TypeScript, Python, contract, state and model-transport fault fixtures.
- US-1.7: disposable database and Compose guards, and any `supabase/` or `infra/` content.
- US-2.2: OpenAPI and TypeScript client generation, and a generator dependency.
- US-2.5: the working FastAPI and BFF processes, and the Luma shell. The placeholder page claims no design-system behavior.
- US-2.6 and US-3.4: the OpenRouter factory and live route qualification. Tool, stream and reasoning round trips stay unqualified.
- Vitest, React Testing Library and Playwright, which the story that first has behavior to test introduces.
- Global tools, `corepack enable`, new runtimes, and any shell or `PATH` configuration.

## Capabilities

### New Capabilities
- `locked-toolchains`: pinned, locked and reproducible Node and Python environments with minimal non-feature packages, and verification that leaves them unchanged.

### Modified Capabilities

None. `openspec list --specs` lists `development-assistant-assets` and `repository-prerequisite-inventory`, and neither covers this behavior.

## Observed Current State

Observed by the Planner on 2026-11-05. The Implementer and Tester re-probe, and none of this is acceptance evidence. Dry runs happened in the session scratch directory, not in this repository.

| Item | Observed | Evidence | Remaining |
|---|---|---|---|
| Scaffold paths | `apps`, `services`, `packages`, `contracts`, `supabase` and `infra` do not exist; 0 tracked files under them | `ls -d`, `git ls-files` | All in scope except `supabase` and `infra` |
| Python 3.12 | 3.12.16 at `/opt/homebrew/bin/python3.12` | Probe | Nothing to install. Pin it |
| uv | 0.13.6 (Homebrew) and 0.11.18 (`~/.local/bin`) | Probe | `required-version` rejected 0.11.18 in a scratch project |
| Node | 26.13.0 through `/usr/bin/env node`; 22.23.2 under nvm | Probe | OQ-2 |
| pnpm | Absent; `which -a pnpm` exits 1 | Probe | OQ-3 |
| Corepack | Only under the nvm Node installs, starts through `/usr/bin/env node` | `ls -l`; inventory | Must run with the pinned Node first on its process `PATH` |
| Python candidates | The 9 PRD pins resolve together: 80 packages for this platform, with `openrouter` 0.11.46, `pydantic` 2.12.5 and `langchain-core` 1.7.6 | `uv pip compile --no-build` dry run, no lock kept | A dry run is not a lock or a qualification |
| Anthropic and Google SDKs | That resolution includes `anthropic` 2.5.0, `langchain-anthropic` 1.7.10, `google-genai` 2.34.0 and `langchain-google-genai` 4.4.3, because `deepagents` 0.7.32 requires both adapters | Dry run; wheel `METADATA`, wheel SHA-256 matching `research/openrouter-langchain-sdk.json` | **OQ-1: conflicts with DH-01** |
| Node candidates | `next` 16.4.5 and `react` 19.3.1 are the shared candidates. Latest `typescript` 7.0.2 and `eslint` 10.14.0 fall outside peer ranges in `eslint-config-next` 16.4.5's dependencies | npm registry metadata, 2026-11-05 | See design D2. No Node resolver has run |
| Existing ignores | `.venv/`, `node_modules/`, `.next/`, `.pnpm-store/`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/` and `*.tsbuildinfo` match sample paths under the new locations | `git check-ignore -v --no-index` | `.corepack/`, `.uv/`, `.cache/` and `next-env.d.ts` have no rule |
| Pending profiles | `fast`, `full`, `db` and `operations` return `not_implemented` by reading `scripts/verify.py`; earlier evidence records exit 2 | Read | Must stay so |
| Skill guidance | `autobots-python` already says checks must not sync or install | Read | Stated, not enforced |

**Already satisfied:** the Python 3.12 interpreter, a uv of a suitable version, a Node 22 install and the ignore rules listed above. These are present rather than qualified, so tests still cover them.

## Decisions This Proposal Does Not Make

OQ-1 to OQ-3 were decided by the user on 2026-11-05, each as recommended. See `implementation-plan.md`.

## Impact

- **New paths:** root manifests and lock, `services/agent/`, `apps/web/`, `packages/`, `contracts/generated/`, `scripts/toolchain.py`, `tests/toolchain/` and one runbook.
- **Protected path:** `.gitignore`.
- **Downloads:** pinned development dependencies from PyPI and npm during `lock` and `bootstrap`, the bootstrap operation DH-01 permits. No application model call, service, database or credential.
- **Unchanged:** `scripts/verify.py`, `scripts/harness_lib.py`, `scripts/specs.py`, `scripts/story_manifest.py`, `tests/harness/`, `.claude/settings.json`, `.claude/autobots.json` and `.claude/hooks/dispatch.py`.
- **Rollback:** revert the story commit, then delete the ignored environment and cache directories named in the runbook.
