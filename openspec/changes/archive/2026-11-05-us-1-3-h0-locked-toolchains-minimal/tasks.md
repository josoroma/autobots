# Tasks

## 1. Resolve and lock the toolchains (US-1.3#1)

- [x] 1.1 Create `services/agent/pyproject.toml` and `services/agent/.python-version` with design D2's Python pins, `requires-python`, `required-version` and strict tool configuration; verify with `test_manifests.py` in task 1.4
- [x] 1.2 Create `./package.json`, `./pnpm-workspace.yaml`, `./.node-version`, `apps/web/package.json`, `packages/api-client/package.json` and `packages/db-types/package.json` with D2's Node pins and D3's and D5's settings; verify with task 1.4
- [x] 1.3 Implement `scripts/toolchain.py` verbs `versions`, `lock` and `bootstrap` with D1's process-scoped runtime selection and D3's repository-local state, then run `lock` and `bootstrap`; verify that `services/agent/uv.lock` and `./pnpm-lock.yaml` exist and `versions` exits 0 reporting the pins while `/usr/bin/env node` still starts Node 26
- [x] 1.4 Add `tests/toolchain/test_manifests.py`: every direct dependency is pinned without a range, the locks hold the PRD versions and OpenRouter and Pydantic bounds, `langsmith` is not direct, and the runbook names each pin; verify it passes and that a paired altered-pin fixture fails
- [x] 1.5 Author the `.gitignore` lines from D3, returned under a heading naming `./.gitignore` and stating what could not be tested; after the coordinator persists them verify each sample with `git check-ignore -q --no-index`, that both locks are not ignored, and that `git status --short --untracked-files=all` lists no generated output after `bootstrap` and `check`

## 2. Create only the scaffolding harness qualification needs (US-1.3#2)

- [x] 2.1 Create the D6 Python package with `services/agent/tests/test_app_factory.py`; verify `create_app().openapi()` has empty `paths` with sockets blocked and no credential, and an async test enters and leaves the lifespan under `pytest-asyncio`
- [x] 2.2 Add `services/agent/tests/test_environment.py`; verify with sockets blocked that the nine selected packages import at their pinned versions, a message and a Pydantic model round-trip through the LangGraph serializer and JSON, and no model is constructed
- [x] 2.3 Create the D7 web shell under `apps/web/`; verify `lint`, `format:check`, `typegen`, `typecheck` and `build` each exit 0 under the pinned Node
- [x] 2.4 Create the generated-contract locations in D7; verify each README names its owning story and that no generated artifact exists
- [x] 2.5 Add `tests/toolchain/test_scaffold_scope.py`: an allow-list of paths under the scaffold roots, no `supabase/` or `infra/`, no product imports or dependencies; verify it passes and that a paired extra-path and extra-dependency fixture fails

## 3. Keep verification non-mutating and prove reproducibility

- [x] 3.1 Implement `scripts/toolchain.py check` per D5, including its guard; verify it exits 0 on the prepared tree and that an independent `shasum` and `git status` snapshot around it shows no difference
- [x] 3.2 Add `tests/toolchain/test_non_mutating.py` with negative tests N1 to N7 from the plan on a disposable copy; verify each fails for its stated reason and leaves the stated files unchanged
- [x] 3.3 Add `tests/toolchain/test_reproducible.py`: fresh-cache `bootstrap` of a disposable copy, then compare installed sets and lock hashes with the real tree and run `check` there; verify they are equal and `check` exits 0
- [x] 3.4 Confirm `harness` is independent: `scripts/verify.py`, `scripts/harness_lib.py`, `scripts/specs.py`, `scripts/story_manifest.py`, `.claude/hooks/dispatch.py`, `.claude/settings.json`, `.claude/autobots.json` and `tests/harness` are unchanged, `harness` passes with a process `PATH` lacking uv and Node, and `--profile fast` and `--profile full` still exit 2
- [x] 3.5 Write `docs/engineering/runbooks/toolchains.md` with prerequisites, target identity, commands, expected checkpoints, failure symptoms, recovery, cleanup ownership and the pinned versions, linking to `docs/engineering/evidence/US-1.3/summary.md` for exercise status, and add one pointer sentence to `docs/engineering/runbooks/development-harness.md`; verify every documented command ran as written, and report any that did not
- [x] 3.6 Integration run: `python3.12 scripts/toolchain.py check`, `python3.12 -m unittest discover -s tests/toolchain -p 'test_*.py' -v`, `python3.12 scripts/specs.py validate` and `python3.12 scripts/verify.py --profile harness`; verify all exit 0 with nonzero test counts, reported as local evidence that establishes neither H0, H1 nor product acceptance
