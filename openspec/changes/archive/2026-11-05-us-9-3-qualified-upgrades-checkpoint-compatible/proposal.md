## Why

US-9.3 needs upgrades that keep saved runs under the semantics they were admitted with, or stop them honestly, and framework adapter changes that are qualified before saved work continues.

## What Changes

- Each run records an execution contract (graph state and tool versions) at admission. A migration records it for saved runs, leaving bindings alone.
- A worker pauses a run its release can't honor, before any model or checkpoint, with `incompatible_version`. Resume refuses it, and a linked new run is the way forward.
- The installed checkpoint adapter has an identity, and a migration records which identities are qualified. An unqualified one stops claims and admission.
- A worker on another model now pauses a saved run instead of failing it, so a release can't destroy saved work this way.
- Tracing-off is also enforced at agent construction, found while testing this.
- Upgrade runbook, exercised by `scripts/qualify_upgrade.py` from a prior release read out of git history.

## Capabilities

### New Capabilities

- `qualified-upgrades`: version checks, forward paths and adapter qualification.

### Modified Capabilities

None.

## Impact

Migration `20261105000025_execution_contracts.sql`, `goal_loop`, `runs`, `checkpoints`, Operations, `scripts/qualify_upgrade.py`, `docs/engineering/runbooks/upgrade.md`.
