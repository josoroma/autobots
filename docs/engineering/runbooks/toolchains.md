# Runbook: pinned Node and Python toolchains

## Scope and target identity

Prepares and checks the pinned Node/pnpm and Python 3.12/uv environments of this repository, on this Mac. Other platforms are unqualified. The target is the working tree the commands run from, or the tree named by `--project-root`. Every result covers that tree only.

`scripts/toolchain.py check` is this story's verification command. The `fast` and `full` profiles of `scripts/verify.py` run these same steps; see [the harness runbook](development-harness.md). `harness` neither needs nor covers these environments. No command here calls a model, starts a service or touches a database. Passing establishes neither H0, H1 nor product acceptance, and tool, stream, reasoning and real-route qualification stay with US-3.4.

## Prerequisites

Nothing here installs a runtime. All of these must already exist:

- `python3.12` reporting exactly the Python pin on the process search path.
- `uv` reporting exactly the uv pin on the process search path. Older copies elsewhere on the path are skipped.
- `node` reporting exactly the Node pin with `corepack` beside it, either on the process search path or under `~/.nvm/versions/node/v<pin>/bin`.
- Network access to PyPI and the npm registry, for `lock`, `bootstrap` and the disposable tests only.

The selected Node directory is put first on `PATH` for child processes only. `/usr/bin/env node` in your own shell keeps starting whatever it did before. pnpm stays out of your shell: there is no `corepack enable`, and `command -v pnpm` still exits 1.

## Pinned versions

The locks are the full record: `services/agent/uv.lock` and `pnpm-lock.yaml`. `python3.12 scripts/toolchain.py versions` prints what is pinned, locked and actually running.

| Runtime or tool | Pin | Set in |
|---|---|---|
| `node` | 22.23.2 | `.node-version`, `engines` |
| `pnpm` | 12.16.1, with a hash | `packageManager`, `engines` |
| `python` | 3.12.16 | `services/agent/.python-version` |
| `uv` | 0.13.6 | `required-version` |

| Python package | Pin |
|---|---|
| `deepagents` | 0.7.32 |
| `langchain` | 1.4.8 |
| `langgraph` | 1.2.19 |
| `langchain-openrouter` | 0.2.9 |
| `openrouter` | 0.11.46 |
| `langgraph-checkpoint-postgres` | 3.2.0 |
| `fastapi` | 0.162.0 |
| `psycopg` | 3.3.8, with the `binary` extra |
| `psycopg-pool` | 3.3.3 |
| `cryptography` | 50.0.2 |
| `pyjwt` | 2.15.1 |
| `httpx` | 0.28.1 |
| `uvicorn` | 0.54.0 |
| `langchain-mcp-adapters` | 0.3.2 |
| `ruff` | 0.17.3 |
| `mypy` | 2.4.1 |
| `pytest` | 9.2.0 |
| `pytest-asyncio` | 1.4.1.post1 |

| Node package | Pin |
|---|---|
| `next` | 16.4.5 |
| `@autobots/api-client` | workspace:* |
| `class-variance-authority` | 0.7.1 |
| `clsx` | 2.1.1 |
| `lucide-react` | 1.69.0 |
| `next-themes` | 0.4.6 |
| `@supabase/ssr` | 0.12.7 |
| `@supabase/supabase-js` | 2.119.0 |
| `tailwind-merge` | 3.7.0 |
| `@axe-core/playwright` | 4.14.0 |
| `@playwright/test` | 1.64.1 |
| `@tailwindcss/postcss` | 4.3.4 |
| `tailwindcss` | 4.3.4 |
| `react` | 19.3.1 |
| `react-dom` | 19.3.1 |
| `typescript` | 6.0.3 |
| `eslint` | 9.39.5 |
| `eslint-config-next` | 16.4.5 |
| `prettier` | 3.9.10 |
| `@types/react` | 19.3.0 |
| `@types/react-dom` | 19.3.0 |
| `@types/node` | 22.20.5 |

`deepagents` 0.7.32 requires the Anthropic and Google adapters, so `anthropic`, `langchain-anthropic`, `google-genai` and `langchain-google-genai` are locked as unused transitive dependencies. Owned code never imports them and `tests/toolchain/test_scaffold_scope.py` enforces that. `langsmith` also stays transitive. `eslint` and `typescript` are deliberately behind latest, because newer majors fall outside the peer ranges of `eslint-config-next` and `typescript-eslint`.

## Commands

Run from the repository root.

### Prepare

```sh
python3.12 scripts/toolchain.py versions
python3.12 scripts/toolchain.py bootstrap
python3.12 scripts/toolchain.py versions
```

Expected: `bootstrap` prints `PASS: python_install` and `PASS: node_install` and exits 0, both locks are unchanged, and `git status --short --untracked-files=all` shows no generated output. Before it, `versions` exits 0 with null `through_package_script` and `through_corepack`, because it never fetches pnpm. After it, they report `v22.23.2` and `12.16.1` through Corepack.

### Check

```sh
python3.12 scripts/toolchain.py check
jq '.status, [.steps[] | {id, status}], .guard_differences' .checks/toolchain/latest.json
```

Expected: exit 0, `PASS` for `python_lock`, `python_env`, `ruff_check`, `ruff_format`, `mypy`, `pytest`, `node_lock`, `node_version`, `lint`, `format_check`, `typegen`, `typecheck` and `build`, then status `passed` and an empty `guard_differences`. It stops at the first failing step. It exits 1 if a lock, a manifest, a changed non-ignored file or the installed package names differ afterwards, even when every step passed.

To check non-mutation independently, take this snapshot before and after, and compare:

```sh
shasum -a 256 services/agent/uv.lock pnpm-lock.yaml services/agent/pyproject.toml package.json pnpm-workspace.yaml apps/web/package.json
git status --porcelain=v1 --untracked-files=all
ls services/agent/.venv/lib/python3.12/site-packages | grep dist-info
ls node_modules/.pnpm
```

### Test

```sh
python3.12 -m unittest discover -s tests/toolchain -p 'test_*.py' -v
```

Expected: exit 0 with nonzero tests. It takes minutes, because it bootstraps two disposable copies under `.checks/US-1.3/copies/` with fresh caches, and it needs both registries. An unreachable registry fails, and is never a skip. It also needs the real tree bootstrapped, since it compares against it.

### Change a pin

Edit the manifest, then lock explicitly, prepare, and check. `lock` is the only verb that writes a lock.

```sh
python3.12 scripts/toolchain.py lock
python3.12 scripts/toolchain.py bootstrap
python3.12 scripts/toolchain.py check
```

Then update the tables above. `tests/toolchain/test_manifests.py` fails on a pin the runbook does not name.

## What the tools write

All of it is inside the repository and ignored by Git.

| State | Location |
|---|---|
| uv cache | `.uv/cache` |
| Python environment | `services/agent/.venv` |
| pnpm itself | `.corepack` |
| pnpm store | `.pnpm-store` |
| pnpm metadata cache | `.cache/pnpm` |
| pnpm update-check state, and anything else honoring XDG directories | `.cache/xdg` |
| Node packages | `node_modules`, `apps/web/node_modules` |
| Next.js output and type shim | `apps/web/.next`, `apps/web/next-env.d.ts` |
| TypeScript build info | `apps/web/tsconfig.tsbuildinfo` |
| Python tool caches | `services/agent/.ruff_cache`, `.mypy_cache`, `.pytest_cache` |
| Last check report | `.checks/toolchain/latest.json` |

**Known limits.** Tools receive your `HOME`, so a listed-path check cannot rule out every write outside the repository. A run with `HOME` pointed at an empty directory showed exactly one thing outside: Next.js creating the empty directory `~/Library/Preferences/nextjs-nodejs`, which holds no file with telemetry disabled. `TMPDIR` is inherited, so temporary files can land there.

## Failure and recovery

| Symptom | Diagnosis and recovery |
|---|---|
| Exit 2, `<tool> <version> is required and was not found` | The pinned runtime is missing or moved, for example after `brew upgrade`. Install it through your own decision, or change the pin through the procedure above. Never run `uv self update`, which uv's own error suggests, as part of a check |
| Exit 2, `not prepared` | Run `bootstrap` explicitly. `check` never prepares anything |
| `python_lock` fails | A Python manifest changed without a lock. Offline, uv's message mentions disabled network rather than a stale lock. Run `lock` if the edit is intended, otherwise restore the manifest |
| `python_env` fails with `The environment is outdated` | A package was removed or changed, or `services/agent/pyproject.toml` was rewritten, even with identical content: uv tracks that file's change time. Run `bootstrap`. Edits under `src` do not cause this |
| `node_lock` fails | A Node manifest changed without a lock. Run `lock` if the edit is intended, otherwise restore the manifest |
| `node_version` fails | A package script did not start the pinned Node. Report it: the selected directory should be first on the child `PATH` |
| `FAIL: guard: changed: <path>` with passing steps | A step changed that path, which is the failure this guard exists to catch. For `apps/web/tsconfig.json`, `next` is rewriting it: commit the values it wants, keeping `strict`, `noUncheckedIndexedAccess` and `exactOptionalPropertyTypes`. Inspect with `git diff`; do not rerun until it is understood |
| `lint`, `typecheck` or `build` fails | Fix the source. Do not add `ignoreBuildErrors` or weaken `tsconfig.json` |
| `[WARN]` about `stateDir` | Someone added it back to `pnpm-workspace.yaml`, where pnpm 12 ignores it. Remove it |
| A disposable test leaves a copy behind | It was interrupted. Delete the entry under `.checks/US-1.3/copies/` |

## Cleanup and rollback

The developer running these commands owns the environments and caches, which can always be rebuilt from the locks. Cleanup removes only ignored state and leaves both locks.

```sh
rm -rf services/agent/.venv node_modules apps/web/node_modules packages/api-client/node_modules packages/db-types/node_modules .uv .corepack .pnpm-store .cache apps/web/.next apps/web/next-env.d.ts apps/web/tsconfig.tsbuildinfo
```

Expected: `python3.12 scripts/toolchain.py check` then exits 2 with `not prepared`, and `bootstrap` restores it. To roll back the story, revert its commit and run this cleanup. Nothing here modifies a global install, a shell profile, or a Homebrew or nvm directory, so nothing outside the repository needs undoing.

## Evidence and exercise status

Last-exercised revision, date, result, and the steps exercised and left untested are recorded in the change's `verification.md`, archived under `openspec/changes/archive/`, not here.
