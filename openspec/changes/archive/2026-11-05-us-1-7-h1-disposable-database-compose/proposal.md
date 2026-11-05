## Why

Migration and operation tests must never be able to reset persistent workbench data, and SP-002 and DH-A06/A07/A10 require that proved on an isolated target before any product migration exists. This machine also runs unrelated Supabase stacks, so the guard must recognize a disposable target positively.

## What Changes

- `scripts/disposable_db.py`: `reset`, `cleanup` and `migrate` refuse anything but a marked disposable target, before any Docker call that could change it. The target's name, ports, volumes and connection variables are checked first, then the rendered Compose configuration, then labels and a marker row.
- `qualify` creates its own `autobots-disposable-<id>` project with generated secrets, runs synthetic migrations, seeds and authorization cases, removes only what it proves it owns, and compares other Docker resources before and after.
- `infra/disposable/compose.yaml`: Postgres and Storage on loopback, digest-pinned with `pull_policy: never`, with labeled volumes. `tests/db/`: synthetic SQL, not product schema.
- `scripts/verify.py --profile db` runs this. `operations` stays `not_implemented`.

**Limits, by the sources:** these two images are ones already on this machine, not the coordinated self-hosted v0.8.3 release that US-2.1 pins, so this qualifies the wrappers and not that stack. No persistent stack or generated database types exist yet. Fingerprinting and `Stop` gain these inputs but do not require a `db` report.

## Capabilities

### New Capabilities

- `disposable-database-guards`: refused persistent targets and disposable migration, seed and authorization fixtures.

### Modified Capabilities

None.

## Impact

New `scripts/disposable_db.py`, `infra/disposable/`, `tests/db/` and `tests/harness/test_disposable_guard.py`. Updates `scripts/verify.py`, `scripts/harness_lib.py`, `.claude/autobots.json`, `tests/harness/test_hooks.py`, the harness runbook, `AGENTS.md`, `README.md`, the delivery rule, the verify skill and `CODEBASE.md`. Uses Docker with existing local images; nothing is pulled, and nothing persistent is touched.
