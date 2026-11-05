# Implementation Plan — us-1-3-h0-locked-toolchains-minimal

Story: US-1.3
Change: us-1-3-h0-locked-toolchains-minimal

## Selected Story

US-1.3: H0 locked toolchains and minimal scaffolding (EPIC-1, phase reference H0-03). Sources: SP-001, SP-004, SP-017, DH-06, Option B PRD section 3.1, SP-020. Dependency US-1.1 is `DONE`.

Acceptance, quoted from `./SPECS.md`:

```gherkin
Scenario: Resolve the combined environment
  Given the researched package candidates and Python/OpenRouter compatibility constraints
  When pinned Node/pnpm and Python 3.12/uv manifests and locks are resolved
  Then a reproducible prepared environment and minimal non-feature packages exist with recorded versions

Scenario: Keep verification non-mutating
  Given a prepared locked environment
  When a verification command runs
  Then it does not silently install dependencies or rewrite the lock
```

No Given is conditional on the machine's state, so the unmet-Given exception does not apply. The negative tests arrange their conditions in a disposable copy, and the evidence says so.

**Bridge requirements carried here, since specialists may not see the rule.** This plan names `./.gitignore` as protected. The implementer returns that content under a heading naming the path, stating what it could not test; the coordinator writes it verbatim before capture; the reviewer checks it as implementation. Capture runs immediately before every review. Verdicts state `Reviewed fingerprint: <hex>` on its own line, never on the `Verdict:` or `Blocking:` line or in a criterion row. Rigor per the bridge: no architect critique or adversarial checks on this story, and every required gate stays.

## OpenSpec Artifacts

- `openspec/changes/us-1-3-h0-locked-toolchains-minimal/proposal.md`: scope, non-goals and observed state.
- `openspec/changes/us-1-3-h0-locked-toolchains-minimal/specs/locked-toolchains/spec.md`: two requirements, each carrying one of the story's scenarios.
- `openspec/changes/us-1-3-h0-locked-toolchains-minimal/design.md`: runtime selection, pins, tool state, verbs, the `check` guard and scaffold limits.
- `openspec/changes/us-1-3-h0-locked-toolchains-minimal/tasks.md`: sixteen tasks under the story's two tasks, plus the verification group.

A stand-in proposal plus this spec delta passed `openspec validate --strict` on a scratch copy. The persisted artifacts and this plan have not been through a validator, because the Planner writes nothing. After persisting, the coordinator runs `openspec validate us-1-3-h0-locked-toolchains-minimal --strict` and `validate-implementation-plan --story US-1.3 --change us-1-3-h0-locked-toolchains-minimal`.

## Implementation Order

**Coordinator, first:** put OQ-1 to OQ-3 to the user. The bridge's Stopping section applies: run `delivery block --reason` if the answers are not available. Then persist these artifacts and open `docs/engineering/work-items/US-1.3.md`. This plan assumes the recommended options. Another answer changes the plan as Open Questions describes, as an amendment before implementation.

**Implementer, first pass:**

1. Tasks 1.1 and 1.2: manifests first, because `lock` needs them.
2. Task 1.3: `versions`, `lock`, `bootstrap`. This is the first real resolve of both sets. A candidate that does not resolve stops the work and is reported, not replaced.
3. Tasks 2.1, 2.2, 2.3 and 2.4: scaffolding. Task 2.3 includes the first run of the TypeScript and ESLint pins.
4. Tasks 1.4 and 2.5: static tests, once the locks and paths they assert exist.
5. Task 3.1: `check`, needing everything above.
6. Tasks 3.2 and 3.3: disposable-copy tests, using candidate ignore lines in the copy.
7. Task 3.5: runbook, final by the end of the second pass.
8. Task 1.5, first half: observe what runs generated with `git status --short --untracked-files=all`, then return the `./.gitignore` lines. It adds rules for what was observed, from D3 and the coordinator's list: `.eslintcache`, `.coverage`, `coverage/`, `.hypothesis/`, `.cache/`, `.turbo/`, `.uv/`. A listed cache that no tool produced gets no rule. State that `git check-ignore` on the real tree could not be run yet.

**Coordinator:** write the lines verbatim after the existing rules and record the path in the Implementation section. A needed change goes back to the implementer. The harness fingerprint changes with `.gitignore`, so a Stop-hook block between passes is expected.

**Implementer, second pass:**

9. Task 1.5, second half.
10. Task 3.4.
11. Task 3.6, then tick tasks only if their checks passed.

**Coordinator, before review:** write the Implementation section, then run the bridge's capture commands with `.checks/US-1.3/changed.txt`. The reviewer also covers the coordinator's edits to `.claude/rules/ohmyorch-delivery.md` and `docs/engineering/decisions/0002-ohmyorch-delivery-loop.md`, which record the user's 2026-11-05 decisions and land in this story's commit.

**Then:** review, test (the tester exercises the runbook), evidence review, archive, mark-done, commit. `CODEBASE.md`'s statements about pnpm and lockfiles become stale; the coordinator refreshes it at the next `select`.

## Task to Acceptance Mapping

| Task | Acceptance criterion | Notes |
|---|---|---|
| 1.1 Python manifest | Scenario: Resolve the combined environment | "pinned Python 3.12/uv manifests" |
| 1.2 Node manifests | Scenario: Resolve the combined environment | "pinned Node/pnpm manifests" |
| 1.3 `versions`, `lock`, `bootstrap` | Scenario: Resolve the combined environment | "locks are resolved", "prepared environment", "recorded versions" |
| 1.4 Manifest and lock tests | Scenario: Resolve the combined environment | The candidates and constraints in the Given |
| 1.5 Ignore rules | Scenario: Resolve the combined environment; Scenario: Keep verification non-mutating | A prepared environment leaves the tree clean, so a tree difference means something |
| 2.1 Python package | Scenario: Resolve the combined environment | "minimal non-feature packages" |
| 2.2 Environment test | Scenario: Resolve the combined environment | PRD 3.1's import and serialization gate, within the limit stated below |
| 2.3 Web shell | Scenario: Resolve the combined environment | "minimal non-feature packages" |
| 2.4 Contract locations | Scenario: Resolve the combined environment | SP-001 item 3's locations; story task US-1.3#2 |
| 2.5 Scope test | Scenario: Resolve the combined environment | "non-feature" and "minimal" made checkable |
| 3.1 `check` and guard | Scenario: Keep verification non-mutating | The When's verification command |
| 3.2 Negative tests | Scenario: Keep verification non-mutating | Each could fail |
| 3.3 Reproduction | Scenario: Resolve the combined environment | "reproducible" |
| 3.4 Harness independence | Scenario: Keep verification non-mutating | `harness` is also a verification command, and must not depend on these environments |
| 3.5 Runbook | Scenario: Resolve the combined environment; Scenario: Keep verification non-mutating | DH-W05 |
| 3.6 Integration run | Scenario: Resolve the combined environment; Scenario: Keep verification non-mutating | Spans groups |

Mapped: 16 of 16. No unmapped task. The coordinator's bridge and Decision 0002 edits carry no task: they change no acceptance behavior, and the reviewer covers them.

## Affected Files

Likely scope. No scaffold path exists today (`ls -d`, `git ls-files`), so the new rows rest on DH-03's layout and design D3 to D7. `check-write-scope.sh` is what blocks the implementer for the protected row.

| Path | Expected change | Evidence |
|---|---|---|
| `./.gitignore` | **Protected, implementer authors, coordinator persists.** Likely `.corepack/`, `.uv/`, `.cache/`, `next-env.d.ts`, plus anything else observed | `git check-ignore` exit 1 for these samples; Decision 0002's rule that a story introducing a tool adds its ignores |
| `./package.json` | Workspace root: `packageManager`, `engines`, scripts | DH-09 "package scripts implement pinned commands" |
| `./pnpm-workspace.yaml` | Members and settings from D3 and D5 | pnpm settings page |
| `./pnpm-lock.yaml` | Generated by `lock`, tracked | H0.3 |
| `./.node-version` | Pinned Node | D1 |
| `services/agent/pyproject.toml` | Manifest and tool configuration | DH-03 |
| `services/agent/uv.lock` | Generated by `lock`, tracked | DH-03, DH-06 |
| `services/agent/.python-version` | Pinned Python | D1 |
| `services/agent/src/autobots/__init__.py` | Package | DH-03 |
| `services/agent/src/autobots/py.typed` | Typing marker | Strict mypy for owned modules |
| `services/agent/src/autobots/api/__init__.py` | Package | DH-03 |
| `services/agent/src/autobots/api/app.py` | `create_app()`, empty lifespan, no routes | SP-004, DH-06 |
| `services/agent/tests/test_app_factory.py` | Factory and lifespan tests | DH-06 |
| `services/agent/tests/test_environment.py` | Import, version and serialization tests | PRD 3.1 |
| `services/agent/tests/conftest.py` | Socket block, if a fixture is the simplest form | DH-06 |
| `apps/web/package.json` | Web package and scripts | DH-03, DH-09 |
| `apps/web/tsconfig.json` | Strict settings | DH-06 |
| `apps/web/next.config.ts` | Minimal, no error suppression | DH-06 |
| `apps/web/eslint.config.mjs` | `eslint-config-next` | DH-06 |
| `apps/web/app/layout.tsx` | Static root layout | SP-001 item 3 |
| `apps/web/app/page.tsx` | Static placeholder | SP-001 item 3 |
| `packages/api-client/package.json` | Private placeholder | DH-03 |
| `packages/api-client/README.md` | Generated-output note, US-2.2 | SP-001 item 3 |
| `packages/db-types/package.json` | Private placeholder | DH-03 |
| `packages/db-types/README.md` | Generated-output note, naming the owning story | SP-001 item 3 |
| `contracts/generated/README.md` | Location note, US-2.2 | SP-001 item 3 |
| `scripts/toolchain.py` | Verbs from D4 and D5 | No existing script prepares or checks these |
| `tests/toolchain/support.py` | Disposable-copy arrangement | Design D8 |
| `tests/toolchain/test_manifests.py` | Pin and candidate tests | Task 1.4 |
| `tests/toolchain/test_scaffold_scope.py` | Allow-list tests | Task 2.5 |
| `tests/toolchain/test_non_mutating.py` | N1 to N7 | Task 3.2 |
| `tests/toolchain/test_reproducible.py` | Reproduction test | Task 3.3 |
| `docs/engineering/runbooks/toolchains.md` | New DH-W05 procedure | DH-W05 |
| `docs/engineering/runbooks/development-harness.md` | One pointer sentence under its prerequisites | Read: it says application dependency qualification is separate. `tests/harness/test_assistant_assets.py` was grepped and asserts no runbook text there |
| `.claude/rules/ohmyorch-delivery.md` | Coordinator edit already in the tree, the 2026-11-05 rulings | `git status`; coordinator's notes |
| `docs/engineering/decisions/0002-ohmyorch-delivery-loop.md` | Coordinator edit already in the tree, the 2026-11-05 rulings | `git status`; coordinator's notes |
| `./SPECS.md` | Coordinator-owned status and task edits | Bridge rule |
| `./CODEBASE.md` | Coordinator-owned; revision already refreshed | `git status`; bridge rule |
| `openspec/changes/us-1-3-h0-locked-toolchains-minimal/` | Implementer ticks `tasks.md`; coordinator owns planning files and `status.md`; reviewer and tester add verdicts | Directory listing; write-scope script |
| `openspec/delivery/goal.md` | Coordinator-owned derived state | `git status` |
| `openspec/specs/locked-toolchains/spec.md` | Created by `archive` | Earlier stories' capabilities under `openspec/specs/` |
| `docs/engineering/work-items/US-1.3.md` | Coordinator-owned DH-W record | Bridge rule |
| `docs/engineering/evidence/US-1.3/` | Coordinator-owned `reviewed-manifest.json`, `summary.md`, `verification.json` and `toolchain-versions.json` | Bridge rule; `is_record()` in `scripts/story_manifest.py` excludes this directory |

**Expected unchanged,** covered by check T2.8: `scripts/verify.py`, `scripts/harness_lib.py`, `scripts/specs.py`, `scripts/story_manifest.py`, `tests/harness/test_hooks.py`, `tests/harness/test_specs.py`, `tests/harness/test_story_manifest.py`, `tests/harness/test_assistant_assets.py`, `.claude/hooks/dispatch.py`, `.claude/settings.json`, `.claude/autobots.json`, `AGENTS.md` and `CLAUDE.md`. Naming them does not authorize a change: a needed change is a plan amendment first.

**What the checks generate, all Git-ignored before capture:**

| Output | Produced by | Rule |
|---|---|---|
| `services/agent/.venv/` | `bootstrap` | Exists: `.venv/` |
| `.uv/cache` | uv | **New:** `.uv/` |
| `.corepack/` | Corepack | **New:** `.corepack/` |
| `.pnpm-store/`, `node_modules/` | pnpm | Exist |
| `.cache/pnpm` and `.cache/pnpm-state` | pnpm | **New:** `.cache/` |
| `apps/web/.next/` | `next typegen`, `next build` | Exists: `.next/` |
| `apps/web/next-env.d.ts` | `next typegen` | **New:** `next-env.d.ts` |
| `*.tsbuildinfo` | `tsc`, if incremental | Exists |
| `.ruff_cache/`, `.mypy_cache/`, `.pytest_cache/`, `__pycache__/` | Python tools | Exist |
| `.checks/toolchain/latest.json`, `.checks/harness/`, `.checks/US-1.3/` | `check`, `harness`, tests and probes | Exists: `.checks/` |

Contract files that must stay tracked, and so must not match a rule: `./pnpm-lock.yaml`, `services/agent/uv.lock`, `apps/web/tsconfig.json`.

**Runbook:** `docs/engineering/runbooks/toolchains.md`, final at capture. Its exercise status lives in `docs/engineering/evidence/US-1.3/summary.md`: last-exercised revision, date, result, steps exercised and steps untested, as the user confirmed on 2026-11-05.

## Test Strategy

Evidence classes are DH-09.2's. Model transport is `none` throughout, and no service or database runs. Nothing here establishes H0, H1 or product acceptance.

- **`static`:** parsing manifests and locks, allow-lists, lint, format and type checks.
- **`disposable`:** runs in a copy under `.checks/US-1.3/`, and pytest and `next build` on local fixtures with no services.
- **`mock`:** the stub mutating tool in N5 only.
- **`live`:** not used. `lock` and `bootstrap` do reach real registries, which the evidence states as bootstrap network use, not live acceptance.

Commands:

```sh
python3.12 scripts/toolchain.py versions
python3.12 scripts/toolchain.py bootstrap
python3.12 scripts/toolchain.py check
python3.12 -m unittest discover -s tests/toolchain -p 'test_*.py' -v
python3.12 scripts/specs.py validate
python3.12 scripts/verify.py --profile harness
```

### Scenario: Resolve the combined environment

Then: "a reproducible prepared environment and minimal non-feature packages exist with recorded versions".

| ID | Part of the Then | Check | Expected | Class |
|---|---|---|---|---|
| T1.1 | Pinned manifests | `test_manifests.py` parses `services/agent/pyproject.toml` and each `package.json` | Every direct dependency has no range. `packageManager` carries a hash. `requires-python` is `==3.12.*`. `required-version` is `==0.13.6`. An altered-pin fixture makes the same assertion fail | `static` |
| T1.2 | Candidates and constraints | Same test, reading `uv.lock` with `tomllib` and `pnpm-lock.yaml` | Locked `deepagents` 0.7.32, `langchain` 1.4.8, `langgraph` 1.2.19, `langchain-openrouter` 0.2.9, `openrouter` 0.11.46, `langgraph-checkpoint-postgres` 3.2.0, `fastapi` 0.162.0, `psycopg` 3.3.8, `langchain-mcp-adapters` 0.3.2; `pydantic` in `>=2.11.2,<2.13`; `langchain-core` in `>=1.7.4,<2`; `openrouter` below 1.0; `langsmith` absent from direct dependencies; `next` 16.4.5; `react` and `react-dom` 19.3.1 | `static` |
| T1.3 | Reproducible | `test_reproducible.py`: copy to `.checks/US-1.3/`, fresh caches, `bootstrap`, then compare | Lock SHA-256 unchanged and equal to the real tree. `uv pip freeze` equal, apart from the project's own editable line. `node_modules/.pnpm` entry names equal. `check` in the copy exits 0 | `disposable` |
| T1.4 | Prepared environment, combined | `.venv/bin/pytest` running `test_environment.py` with sockets blocked | Nine packages import at their pinned versions. A LangChain message and a Pydantic model round-trip through LangGraph's serializer and JSON. `psycopg` reports the binary implementation with no connection. No model is constructed | `disposable` |
| T1.5 | Prepared environment, runtime | From a shell whose `/usr/bin/env node` starts v26, run `versions`, and have `check` run a Node version step | Node reported as v22.23.2 through the package scripts, while the outer `node` stays v26. `.node-version` changed to an uninstalled version in a copy gives exit 2, with no download | `disposable` |
| T1.6 | Minimal non-feature | `test_scaffold_scope.py`; `.venv/bin/pytest` on `test_app_factory.py` | `git ls-files -co --exclude-standard` under the scaffold roots equals the allow-list, and an extra path fails. No `supabase/` or `infra/`. `openapi()["paths"]` is empty. No import of `deepagents`, `langgraph`, `langchain`, `openrouter`, `psycopg`, `anthropic` or `google` under `services/agent/src`. Web dependencies are only `next`, `react`, `react-dom`, and an added `zod` or `@supabase/*` fails | `static`, `disposable` |
| T1.7 | Packages build and lint | `check`'s Python and Node steps | `ruff check`, `ruff format --check`, `mypy`, `pytest`, `lint`, `format:check`, `typegen`, `typecheck` and `build` all exit 0, with nonzero tests | `static`, `disposable` |
| T1.8 | Recorded versions | `versions` output compared with locks and runbook; `test_manifests.py` greps the runbook for each pin | All match. Output saved as `docs/engineering/evidence/US-1.3/toolchain-versions.json` | `static` |
| T1.9 | Prepared, clean tree | `git check-ignore -q --no-index` per sample; `git status --short --untracked-files=all` after `bootstrap` and `check`; `find` for `.eslintcache`, `.coverage`, `coverage`, `.hypothesis`, `.turbo`, excluding `research` and the environments | Samples from D3 exit 0, both locks and `apps/web/tsconfig.json` exit 1, and status lists only paths in Affected Files. `find` prints nothing, or the path gets a rule through the protected procedure | `static` |
| T1.10 | Scope of machine changes | Before and after the real `bootstrap`: `command -v pnpm`, `ls` of the Node 22.23.2 `bin` directory, and existence and modification time of `~/.cache/uv`, `~/.cache/node/corepack`, `~/Library/pnpm`, `~/Library/Caches/pnpm` and `~/.local/share/pnpm` | `command -v pnpm` still exits 1; no `pnpm` or `pnpx` shim; those paths unchanged. **Limit:** a listed-path check does not rule out a write elsewhere | `static` |

**Limit of T1.4, stated rather than hidden:** this is PRD 3.1's resolver, import and local serialization gate only. The research file also lists stream, reasoning and tool round trips and real-route qualification as release gates, which belong to US-3.4 and are not claimed here.

### Scenario: Keep verification non-mutating

Then: "it does not silently install dependencies or rewrite the lock".

**Independent snapshot.** The tester takes this around each run, separately from `check`'s own guard:

```sh
shasum -a 256 services/agent/uv.lock pnpm-lock.yaml services/agent/pyproject.toml package.json pnpm-workspace.yaml apps/web/package.json
git status --porcelain=v1 --untracked-files=all
ls services/agent/.venv/lib/python3.12/site-packages | grep dist-info
ls node_modules/.pnpm
```

| ID | Check | Expected | Class |
|---|---|---|---|
| T2.1 | Snapshot around `toolchain.py check` on the prepared tree | Exit 0, snapshots byte-identical | `static`, `disposable` |
| T2.2 | Snapshot around `verify.py --profile harness`, `--profile fast`, `--profile full` | Exit 0, 2 and 2 respectively, snapshots identical. `fast` and `full` print `not_implemented` | `static` |
| T2.3, N1 | Stale Python manifest: add `idna==3.20` to the copy's dependencies, then `check` | Exit 1, `python_lock` failed, `uv.lock` hash unchanged, `dist-info` names unchanged | `disposable` |
| T2.4, N2 | Stale Node manifest: add a dependency to the copy's `apps/web/package.json`, then `check` | Exit 1, `node_lock` failed, `pnpm-lock.yaml` hash unchanged, `node_modules/.pnpm` names unchanged | `disposable` |
| T2.5, N3 | No prepared environment: a copy without `.venv`, `node_modules` and `.corepack`, then `check` | Exit 2 before any tool runs. All three still absent afterwards, so nothing installed and pnpm not fetched | `disposable` |
| T2.6, N4 | Drifted environment: `bootstrap` a copy, `uv pip uninstall` one package, then `check` | Exit 1, `python_env` failed, the package still absent | `disposable` |
| T2.7, N5 | Guard against a mutating step: run the guard with stub steps that append to a lock, and that add an entry under `node_modules/.pnpm` in a copy | Exit 1 naming the changed path, though the stub exits 0. Without this failing, the guard is untested | `mock` |
| N6 | Wrong tool: pin mismatch for uv in a copy | Exit 2 naming tool and wanted version. No download | `disposable` |
| N7 | No launchers: scan `check`'s step list and all `package.json` scripts for `uv run`, a `uv sync` lacking `--check`, `npx`, `dlx`, or `pnpm install` lacking `--frozen-lockfile` | None found, and a fixture string containing each makes the scan fail | `static` |
| T2.8 | Harness independence: `git diff --quiet HEAD --` over the Expected-unchanged list; `git ls-files --others --exclude-standard tests/harness`; `env PATH=/usr/bin:/bin /opt/homebrew/bin/python3.12 scripts/verify.py --profile harness` | Exit 0, no output, then exit 0 with `status: passed`, with adapter `inactive` / `unavailable` stated as arranged by the reduced `PATH`. Run plain `harness` last so the report matches | `static`, `disposable` |

N1 to N6 run on one disposable copy built once per test run, with fresh caches, restoring manifests between cases and doing the drift last. An unreachable registry fails the test, and is never a skip. Bytes in `.next`, caches and bytecode may change: the Then concerns dependencies and the lock, so these are not treated as mutation.

### Probe rules for the implementer and tester

- Never read or print `.env` files, the provider master-key file or `.claude/settings.local.json`. Never name the master-key file in a command. No environment dumps and no printing `PATH`. Setting a process-scoped `PATH` for one command is fine.
- The project hook denies `cat`, `head`, `tail`, `less` or `more` on a `.env` path, any command containing the master-key filename, `supabase db reset`, `docker system prune`, `docker volume prune` and Compose or container `down` with volume removal. It also denies file tools on secret paths and edits escaping the workspace. If it denies a command, leave that out and report it; do not rephrase, encode or split it.
- Do not run `supabase --version`, which appears to make an outbound check, or any other Supabase or Docker command. This story needs neither; cite the inventory if a version is wanted. The Claude CLI probe inside `harness` is existing behavior.
- Keep scratch work under `.checks/US-1.3/`. Do not edit `research/upstream`.
- No install outside `toolchain.py lock` and `bootstrap`. No global install, `corepack enable`, new runtime, shell configuration or `uv self update`, the last of which uv's own error suggests when the pin mismatches.

## Dependencies

- US-1.1: `DONE`. Its inventory is `docs/engineering/prerequisite-inventory.md`.
- **User decisions OQ-1 to OQ-3:** block implementation.
- **External:** PyPI and the npm registry, during `lock`, `bootstrap` and the disposable tests. Both answered on 2026-11-05.
- **Local:** `/opt/homebrew/bin/python3.12` at 3.12.16; `/opt/homebrew/bin/uv` at 0.13.6; Node 22.23.2 and its Corepack under nvm.
- **Later stories depending on this:** US-1.4 (with US-1.2).
- **Plan validity:** `scripts/verify.py`'s `harness` and pending-profile behavior, as read at `1515fc7`.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| The user rejects the transitive Anthropic and Google SDKs, and removing them breaks `deepagents` | medium | high | OQ-1 asks before work starts. By reading the wheel, the Anthropic imports are type-only or deferred to the default-model and Anthropic-model paths, but no run has tested removal |
| Importing `deepagents` loads the Anthropic adapter despite that reading | low | medium | T1.4 can record `sys.modules` after import. If loaded, report it, because it weakens OQ-1's recommended reasoning |
| pnpm 12 flag combination or settings behave differently than the documentation pages suggest; none was run | medium | medium | N2 and N3 decide. A mutating substitute is not allowed; design D5 names the alternative |
| Corepack 0.34.6 cannot handle `pnpm@12` | low | medium | Stop and report, since OQ-3's other options then matter. Do not fall back to a global install |
| TypeScript 6.0.3 is rejected by Next.js 16.4.5 | medium | low | Use 5.9.3, which `typescript-eslint` also accepts, and record it. Latest 7.0.2 stays out of range |
| `next build` rewrites `apps/web/tsconfig.json`, a tracked file | medium | medium | The guard fails it. Commit the values Next.js wants, without weakening DH-06's flags |
| A lock lands that the real resolve changed from the dry run, such as a newer transitive | medium | low | Expected: the locks are the record. T1.2 still enforces the PRD pins and bounds |
| A tester reads `harness` success as toolchain proof | low | high | The runbook and evidence separate them. `harness` covers neither the locks nor application paths |
| Next.js writes telemetry configuration outside the repository despite `NEXT_TELEMETRY_DISABLED` | low | low | T1.10 can add its path if seen; report it. Not checked by the Planner |
| The `.nextjs` path-scoped rule's design requirements read as applying to the placeholder page | medium | low | Non-goal names US-2.5 as owner. Reviewer told the page claims no design behavior |
| A test run takes minutes through fresh-cache bootstraps | high | low | Outside `harness`, so its 60-second limit does not apply |

## Open Questions

None open.

Decided by the user on 2026-11-05, and recorded in Decision 0002. All match the recommended options these artifacts assume, so no other change is needed:

- **OQ-1:** the Anthropic and Google SDKs are locked as unused transitive dependencies of `deepagents`. Owned code never imports them, a test enforces it, and the evidence names them.
- **OQ-2:** Node is pinned to 22.23.2, already installed under nvm, selected per process.
- **OQ-3:** pnpm is repo-local through Corepack under the pinned Node, without `corepack enable`, with `COREPACK_HOME` at `.corepack/`. This has not been run. If it fails, stop and report; do not switch to a method that changes the machine.
